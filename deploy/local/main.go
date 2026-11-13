// local starts the LAN demo and advertises its API address to Android over UDP.
package main

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const discoveryPort = 51020
const discoveryPrefix = "IV_DISCOVER_V1 "

func localIP() (string, error) {
	interfaces, err := net.Interfaces()
	if err != nil {
		return "", err
	}
	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 ||
			strings.HasPrefix(iface.Name, "docker") || strings.HasPrefix(iface.Name, "br-") ||
			strings.HasPrefix(iface.Name, "veth") || strings.HasPrefix(iface.Name, "tun") ||
			strings.HasPrefix(iface.Name, "tailscale") || strings.HasPrefix(iface.Name, "Meta") {
			continue
		}
		addresses, err := iface.Addrs()
		if err != nil {
			return "", err
		}
		for _, address := range addresses {
			ip, _, err := net.ParseCIDR(address.String())
			if err == nil && ip.To4() != nil && ip.IsPrivate() {
				return ip.String(), nil
			}
		}
	}
	return "", errors.New("LAN IPv4 не найден; укажите --host")
}

func discoveryResponse(request []byte, apiURL string) []byte {
	text := string(request)
	if !strings.HasPrefix(text, discoveryPrefix) {
		return nil
	}
	nonce := strings.TrimPrefix(text, discoveryPrefix)
	if len(nonce) != 36 {
		return nil
	}
	for _, char := range nonce {
		if !(char >= 'a' && char <= 'f' || char >= '0' && char <= '9' || char == '-') {
			return nil
		}
	}
	result, err := json.Marshal(map[string]string{
		"service": "industrial-vision", "api_url": apiURL, "nonce": nonce,
	})
	if err != nil {
		return nil
	}
	return result
}

func serveDiscovery(ctx context.Context, conn *net.UDPConn, origin string) error {
	client := &http.Client{Timeout: time.Second, Transport: &http.Transport{Proxy: nil}, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	buffer := make([]byte, 256)
	for {
		if err := conn.SetReadDeadline(time.Now().Add(time.Second)); err != nil {
			return err
		}
		count, peer, err := conn.ReadFromUDP(buffer)
		if err != nil {
			if ctx.Err() != nil {
				return nil
			}
			if e, ok := err.(net.Error); ok && e.Timeout() {
				continue
			}
			return err
		}
		response := discoveryResponse(buffer[:count], origin+"/industrial-vision/api/v1/")
		if response == nil {
			continue
		}
		health, err := client.Get(origin + "/healthz")
		if err != nil {
			continue
		}
		health.Body.Close()
		if health.StatusCode != http.StatusOK {
			continue
		}
		if _, err := conn.WriteToUDP(response, peer); err != nil {
			return err
		}
	}
}

func readLocalEnv(path string) (map[string]string, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	values := map[string]string{}
	for _, line := range strings.Split(string(data), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		key, value, ok := strings.Cut(line, "=")
		if !ok {
			return nil, errors.New("некорректная строка в .env.local")
		}
		key, value = strings.TrimSpace(key), strings.TrimSpace(value)
		if len(value) >= 2 && value[0] == '"' && value[len(value)-1] == '"' {
			value, err = strconv.Unquote(value)
			if err != nil {
				return nil, errors.New("некорректные кавычки в .env.local")
			}
		} else if len(value) >= 2 && value[0] == '\'' && value[len(value)-1] == '\'' {
			value = value[1 : len(value)-1]
		}
		values[key] = value
	}
	return values, nil
}

func prepareLocalEnv(path string) error {
	values, err := readLocalEnv(path)
	fresh := os.IsNotExist(err)
	if err != nil && !fresh {
		return err
	}
	if fresh {
		values = map[string]string{}
	}
	var additions strings.Builder
	if fresh {
		additions.WriteString("# Local secrets; never commit.\n")
	} else {
		additions.WriteString("\n")
	}
	added := false
	for _, key := range []string{"IV_LOCAL_DB_PASSWORD", "IV_LOCAL_ADMIN_PASSWORD", "IV_DEMO_PASSWORD", "IV_DEMO_ADMIN_PASSWORD"} {
		if value, ok := values[key]; ok {
			if len(value) < 12 {
				return fmt.Errorf("%s: ожидается пароль не короче 12 символов", key)
			}
			continue
		}
		random := make([]byte, 24)
		if _, err := rand.Read(random); err != nil {
			return err
		}
		fmt.Fprintf(&additions, "%s=%s\n", key, hex.EncodeToString(random))
		added = true
	}
	if !added {
		return nil
	}
	flags := os.O_WRONLY | os.O_APPEND
	if fresh {
		flags = os.O_WRONLY | os.O_CREATE | os.O_EXCL
	}
	file, err := os.OpenFile(path, flags, 0600)
	if err != nil {
		return err
	}
	_, writeErr := file.WriteString(additions.String())
	return errors.Join(writeErr, file.Close())
}

type apkManifest struct {
	SourceSHA string `json:"source_sha256"`
	APKSHA    string `json:"apk_sha256"`
}

func mobileFingerprint(root string) (string, error) {
	hash := sha256.New()
	hash.Write([]byte("industrial-vision-debug-docker-v1\x00"))
	err := filepath.WalkDir(root, func(path string, entry os.DirEntry, walkErr error) error {
		if walkErr != nil {
			return walkErr
		}
		if entry.IsDir() {
			switch entry.Name() {
			case "build", ".gradle", ".kotlin", ".idea":
				return filepath.SkipDir
			}
			return nil
		}
		if entry.Name() == "local.properties" || strings.HasSuffix(entry.Name(), ".apk") || strings.HasSuffix(entry.Name(), ".log") {
			return nil
		}
		if entry.Type()&os.ModeSymlink != 0 {
			return fmt.Errorf("символическая ссылка не поддерживается в Android-сборке: %s", path)
		}
		relative, err := filepath.Rel(root, path)
		if err != nil {
			return err
		}
		hash.Write([]byte(filepath.ToSlash(relative) + "\x00"))
		file, err := os.Open(path)
		if err != nil {
			return err
		}
		_, copyErr := io.Copy(hash, file)
		closeErr := file.Close()
		hash.Write([]byte("\x00"))
		return errors.Join(copyErr, closeErr)
	})
	return hex.EncodeToString(hash.Sum(nil)), err
}

func fileSHA(path string) (string, error) {
	file, err := os.Open(path)
	if err != nil {
		return "", err
	}
	defer file.Close()
	hash := sha256.New()
	if _, err := io.Copy(hash, file); err != nil {
		return "", err
	}
	return hex.EncodeToString(hash.Sum(nil)), nil
}

func cachedAPK(directory, source string) bool {
	data, err := os.ReadFile(filepath.Join(directory, "build-manifest.json"))
	if err != nil {
		return false
	}
	var manifest apkManifest
	if json.Unmarshal(data, &manifest) != nil || manifest.SourceSHA != source {
		return false
	}
	hash, err := fileSHA(filepath.Join(directory, "app-debug.apk"))
	return err == nil && manifest.APKSHA == hash
}

func writeJSON(path string, value any) error {
	data, err := json.Marshal(value)
	if err != nil {
		return err
	}
	file, err := os.CreateTemp(filepath.Dir(path), ".iv-state-*")
	if err != nil {
		return err
	}
	defer os.Remove(file.Name())
	if _, err := file.Write(data); err != nil {
		file.Close()
		return err
	}
	if err := file.Chmod(0644); err != nil {
		file.Close()
		return err
	}
	if err := file.Close(); err != nil {
		return err
	}
	return os.Rename(file.Name(), path)
}

func buildAPK(ctx context.Context, directory, source string) error {
	temp, err := os.MkdirTemp("", "industrial-vision-apk-*")
	if err != nil {
		return err
	}
	defer os.RemoveAll(temp)
	cmd := exec.CommandContext(ctx, "docker", "build", "--platform", "linux/amd64",
		"--file", "mobile/Dockerfile", "--output", "type=local,dest="+temp, "mobile")
	cmd.Stdout, cmd.Stderr = os.Stdout, os.Stderr
	if err := cmd.Run(); err != nil {
		return err
	}
	current, err := mobileFingerprint("mobile")
	if err != nil {
		return err
	}
	if current != source {
		return errors.New("Android-код изменился во время сборки; повторите запуск")
	}
	input, err := os.Open(filepath.Join(temp, "app-debug.apk"))
	if err != nil {
		return err
	}
	defer input.Close()
	output, err := os.CreateTemp(directory, ".iv-apk-*")
	if err != nil {
		return err
	}
	defer os.Remove(output.Name())
	_, copyErr := io.Copy(output, input)
	permissionErr := output.Chmod(0644)
	closeErr := output.Close()
	if err := errors.Join(copyErr, permissionErr, closeErr); err != nil {
		return err
	}
	if err := os.Rename(output.Name(), filepath.Join(directory, "app-debug.apk")); err != nil {
		return err
	}
	hash, err := fileSHA(filepath.Join(directory, "app-debug.apk"))
	if err != nil {
		return err
	}
	return writeJSON(filepath.Join(directory, "build-manifest.json"), apkManifest{source, hash})
}

func waitReady(ctx context.Context, origin string) error {
	ctx, cancel := context.WithTimeout(ctx, 90*time.Second)
	defer cancel()
	client := &http.Client{Timeout: time.Second, Transport: &http.Transport{Proxy: nil}}
	for {
		if err := ctx.Err(); err != nil {
			return fmt.Errorf("сервер не запустился: %w", err)
		}
		request, err := http.NewRequestWithContext(ctx, http.MethodGet, origin+"/healthz", nil)
		if err != nil {
			return err
		}
		response, err := client.Do(request)
		if err == nil {
			response.Body.Close()
			if response.StatusCode == http.StatusOK {
				return nil
			}
		}
		timer := time.NewTimer(500 * time.Millisecond)
		select {
		case <-ctx.Done():
			timer.Stop()
		case <-timer.C:
		}
	}
}

func runLocal() (result error) {
	host := flag.String("host", "", "LAN IPv4; by default choose a private address")
	setupOnly := flag.Bool("setup-only", false, "start, provision, wait for APK and exit without UDP discovery")
	skipAPK := flag.Bool("skip-apk", false, "skip APK build, use a previously built artifact")
	flag.Parse()
	if *host == "" {
		ip, err := localIP()
		if err != nil {
			return err
		}
		*host = ip
	}
	ip := net.ParseIP(*host)
	if ip == nil || ip.To4() == nil || !ip.IsPrivate() {
		return errors.New("--host должен быть локальным IPv4")
	}
	if _, err := os.Stat("compose.local.yaml"); err != nil {
		return errors.New("запустите из корня проекта")
	}
	if err := os.Mkdir(".iv-local-lock", 0700); err != nil {
		return fmt.Errorf("локальный запуск уже занят (.iv-local-lock): %w", err)
	}
	defer func() { result = errors.Join(result, os.Remove(".iv-local-lock")) }()
	if err := prepareLocalEnv(".env.local"); err != nil {
		return err
	}
	values, err := readLocalEnv(".env.local")
	if err != nil {
		return err
	}
	directory := filepath.Join("mobile", "app", "build", "outputs", "apk", "debug")
	if err := os.MkdirAll(directory, 0755); err != nil {
		return err
	}
	source, err := mobileFingerprint("mobile")
	if err != nil {
		return err
	}
	origin := "http://" + ip.String() + ":8001"
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	var workers sync.WaitGroup
	defer func() { stop(); workers.Wait() }()
	var conn *net.UDPConn
	if !*setupOnly {
		conn, err = net.ListenUDP("udp4", &net.UDPAddr{Port: discoveryPort})
		if err != nil {
			return err
		}
		defer conn.Close()
	}
	apkDone := make(chan error, 1)
	statePath := filepath.Join(directory, "build-status.json")
	if *skipAPK || cachedAPK(directory, source) {
		state := "MISSING"
		if _, err := os.Stat(filepath.Join(directory, "app-debug.apk")); err == nil {
			state = "READY"
		}
		if err := writeJSON(statePath, map[string]string{"state": state}); err != nil {
			return err
		}
		fmt.Println("APK: используем готовый файл, пересборка не требуется.")
		apkDone <- nil
	} else {
		if err := writeJSON(statePath, map[string]string{"state": "BUILDING"}); err != nil {
			return err
		}
		fmt.Println("APK собирается параллельно. Сайт запустится независимо от этой сборки.")
		workers.Add(1)
		go func() {
			defer workers.Done()
			buildErr := buildAPK(ctx, directory, source)
			state := "READY"
			if buildErr != nil {
				state = "ERROR"
			}
			stateErr := writeJSON(statePath, map[string]string{"state": state})
			apkDone <- errors.Join(buildErr, stateErr)
		}()
	}
	composeArgs := []string{"compose", "--env-file", ".env.local", "-p", "iv-local", "-f", "compose.local.yaml"}
	env := []string{}
	for _, entry := range os.Environ() {
		if !strings.HasPrefix(entry, "IV_LOCAL_BIND=") && !strings.HasPrefix(entry, "IV_LOCAL_ORIGIN=") {
			env = append(env, entry)
		}
	}
	env = append(env, "IV_LOCAL_BIND="+ip.String(), "IV_LOCAL_ORIGIN="+origin)
	cmd := exec.CommandContext(ctx, "docker", append(append([]string{}, composeArgs...), "up", "-d", "--build")...)
	cmd.Env, cmd.Stdout, cmd.Stderr, cmd.Stdin = env, os.Stdout, os.Stderr, os.Stdin
	if err := cmd.Run(); err != nil {
		return err
	}
	if err := waitReady(ctx, origin); err != nil {
		return err
	}
	credentials, err := json.Marshal(map[string]string{"employee_password": values["IV_DEMO_PASSWORD"], "admin_password": values["IV_DEMO_ADMIN_PASSWORD"]})
	if err != nil {
		return err
	}
	bootstrap := exec.CommandContext(ctx, "docker", append(append([]string{}, composeArgs...), "exec", "-T", "backend", "python", "-m", "app.manage", "bootstrap-local")...)
	bootstrap.Env, bootstrap.Stdin, bootstrap.Stdout, bootstrap.Stderr = env, strings.NewReader(string(credentials)), os.Stdout, os.Stderr
	if err := bootstrap.Run(); err != nil {
		return err
	}
	fmt.Println("\nСайт:", origin+"/industrial-vision/")
	fmt.Println("Администратор: demo_admin")
	fmt.Println("Пароль администратора:", values["IV_DEMO_ADMIN_PASSWORD"])
	fmt.Println("Android: pump_worker / pump_engineer")
	fmt.Println("Пароль сотрудников:", values["IV_DEMO_PASSWORD"])
	fmt.Println("Демонасос: pump_demo_001, три компонента. Пароли сохранены в .env.local.")
	fmt.Println("Состояние сборки и скачивание APK — на сайте.")
	if *setupOnly {
		if err := <-apkDone; err != nil {
			return err
		}
		return nil
	}
	discoveryDone := make(chan error, 1)
	workers.Add(1)
	go func() { defer workers.Done(); discoveryDone <- serveDiscovery(ctx, conn, origin) }()
	fmt.Println("Оставьте терминал открытым для быстрого поиска сервера. Ctrl+C остановит поиск и сборку; сайт останется запущен.")
	for {
		select {
		case <-ctx.Done():
			return nil
		case err := <-discoveryDone:
			return err
		case err := <-apkDone:
			if err != nil {
				return fmt.Errorf("сборка APK завершилась ошибкой; сайт продолжает работать: %w", err)
			}
			fmt.Println("APK доступен:", origin+"/industrial-vision/android.apk")
			apkDone = nil
		}
	}
}

func main() {
	if err := runLocal(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		var exit *exec.ExitError
		if errors.As(err, &exit) {
			os.Exit(exit.ExitCode())
		}
		os.Exit(1)
	}
}

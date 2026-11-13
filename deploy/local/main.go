// local starts the LAN demo and advertises its API address to Android over UDP.
package main

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"net"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"strings"
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

func prepareLocalEnv(path string) error {
	if _, err := os.Stat(path); err == nil {
		return nil
	} else if !os.IsNotExist(err) {
		return err
	}
	random := func() (string, error) {
		data := make([]byte, 24)
		if _, err := rand.Read(data); err != nil {
			return "", err
		}
		return hex.EncodeToString(data), nil
	}
	db, err := random()
	if err != nil {
		return err
	}
	admin, err := random()
	if err != nil {
		return err
	}
	demo, err := random()
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if err != nil {
		return err
	}
	_, writeErr := fmt.Fprintf(f, "# Local secrets; never commit.\nIV_LOCAL_DB_PASSWORD=%s\nIV_LOCAL_ADMIN_PASSWORD=%s\nIV_DEMO_PASSWORD=%s\n", db, admin, demo)
	closeErr := f.Close()
	return errors.Join(writeErr, closeErr)
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

func runLocal() error {
	host := flag.String("host", "", "LAN IPv4; by default choose a private address")
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
	if err := prepareLocalEnv(".env.local"); err != nil {
		return err
	}
	if err := os.MkdirAll("mobile/app/build/outputs/apk/debug", 0755); err != nil {
		return err
	}
	origin := "http://" + ip.String() + ":8001"
	// Bind before starting containers so a busy discovery port fails explicitly.
	conn, err := net.ListenUDP("udp4", &net.UDPAddr{Port: discoveryPort})
	if err != nil {
		return err
	}
	defer conn.Close()
	cmd := exec.Command("docker", "compose", "--env-file", ".env.local", "-p", "iv-local", "-f", "compose.local.yaml", "up", "-d", "--build")
	for _, entry := range os.Environ() {
		if !strings.HasPrefix(entry, "IV_LOCAL_BIND=") && !strings.HasPrefix(entry, "IV_LOCAL_ORIGIN=") {
			cmd.Env = append(cmd.Env, entry)
		}
	}
	cmd.Env = append(cmd.Env, "IV_LOCAL_BIND="+ip.String(), "IV_LOCAL_ORIGIN="+origin)
	cmd.Stdout, cmd.Stderr, cmd.Stdin = os.Stdout, os.Stderr, os.Stdin
	if err := cmd.Run(); err != nil {
		return err
	}
	fmt.Println("API:", origin+"/industrial-vision/api/v1/")
	fmt.Println("Поиск сервера Android: UDP 51020. Оставьте эту команду работающей.")
	fmt.Println("Ctrl+C остановит поиск; контейнеры продолжат работать.")
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	return serveDiscovery(ctx, conn, origin)
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

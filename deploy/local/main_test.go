package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestDiscoveryReplyRequiresProtocolAndNonce(t *testing.T) {
	url := "http://192.168.1.50:8001/industrial-vision/api/v1/"
	nonce := "0c9d650e-dd0f-4355-a139-5885f392b162"
	for _, invalid := range []string{"", "other " + nonce, discoveryPrefix + "invalid", discoveryPrefix + strings.Repeat("z", 36)} {
		if discoveryResponse([]byte(invalid), url) != nil {
			t.Fatal("invalid request accepted")
		}
	}
	var reply map[string]string
	if err := json.Unmarshal(discoveryResponse([]byte(discoveryPrefix+nonce), url), &reply); err != nil {
		t.Fatal(err)
	}
	if reply["nonce"] != nonce || reply["api_url"] != url || reply["service"] != "industrial-vision" {
		t.Fatal(reply)
	}
}

func TestLocalSecretsAreCreatedOnce(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".env.local")
	if err := prepareLocalEnv(path); err != nil {
		t.Fatal(err)
	}
	first, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := prepareLocalEnv(path); err != nil {
		t.Fatal(err)
	}
	second, _ := os.ReadFile(path)
	if string(first) != string(second) {
		t.Fatal("credentials were replaced")
	}
	info, _ := os.Stat(path)
	if info.Mode().Perm() != 0600 {
		t.Fatal("secrets permissions")
	}
	for _, key := range []string{"IV_LOCAL_DB_PASSWORD=", "IV_LOCAL_ADMIN_PASSWORD=", "IV_DEMO_PASSWORD="} {
		if !strings.Contains(string(first), key) {
			t.Fatal(key)
		}
	}
}

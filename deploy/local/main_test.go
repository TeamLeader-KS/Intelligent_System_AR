package main

import (
	"bytes"
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

func TestLegacyEnvAddsOnlyMissingSecrets(t *testing.T) {
	path := filepath.Join(t.TempDir(), ".env.local")
	original := "IV_LOCAL_DB_PASSWORD=original-db-password\nIV_LOCAL_ADMIN_PASSWORD=original-db-admin\nIV_DEMO_PASSWORD=original-employee-password\n# keep this comment\n"
	if err := os.WriteFile(path, []byte(original), 0600); err != nil {
		t.Fatal(err)
	}
	if err := prepareLocalEnv(path); err != nil {
		t.Fatal(err)
	}
	updated, _ := os.ReadFile(path)
	if !bytes.HasPrefix(updated, []byte(original)) {
		t.Fatal("existing configuration changed")
	}
	values, err := readLocalEnv(path)
	if err != nil || len(values["IV_DEMO_ADMIN_PASSWORD"]) != 48 {
		t.Fatal("admin secret not generated", err)
	}
	if err := prepareLocalEnv(path); err != nil {
		t.Fatal(err)
	}
	again, _ := os.ReadFile(path)
	if !bytes.Equal(updated, again) {
		t.Fatal("restart changed credentials")
	}
}

func TestMobileFingerprintIgnoresBuildOutputButTracksSources(t *testing.T) {
	root := t.TempDir()
	if err := os.WriteFile(filepath.Join(root, "build.gradle.kts"), []byte("source v1"), 0600); err != nil {
		t.Fatal(err)
	}
	first, err := mobileFingerprint(root)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir(filepath.Join(root, "build"), 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "build", "generated.kt"), []byte("generated"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "local.properties"), []byte("sdk.dir=local"), 0600); err != nil {
		t.Fatal(err)
	}
	same, _ := mobileFingerprint(root)
	if first != same {
		t.Fatal("generated output changed fingerprint")
	}
	if err := os.WriteFile(filepath.Join(root, "build.gradle.kts"), []byte("source v2"), 0600); err != nil {
		t.Fatal(err)
	}
	changed, _ := mobileFingerprint(root)
	if first == changed {
		t.Fatal("source changes were ignored")
	}
}

func TestAPKCacheRequiresMatchingSourcesAndFileHash(t *testing.T) {
	directory := t.TempDir()
	apk := filepath.Join(directory, "app-debug.apk")
	if err := os.WriteFile(apk, []byte("artifact"), 0600); err != nil {
		t.Fatal(err)
	}
	hash, err := fileSHA(apk)
	if err != nil {
		t.Fatal(err)
	}
	if err := writeJSON(filepath.Join(directory, "build-manifest.json"), apkManifest{"sources-v1", hash}); err != nil {
		t.Fatal(err)
	}
	if !cachedAPK(directory, "sources-v1") {
		t.Fatal("valid artifact not reused")
	}
	if cachedAPK(directory, "sources-v2") {
		t.Fatal("stale sources accepted")
	}
	if err := os.WriteFile(apk, []byte("corrupt"), 0600); err != nil {
		t.Fatal(err)
	}
	if cachedAPK(directory, "sources-v1") {
		t.Fatal("modified artifact accepted")
	}
}

func TestModelChangesInvalidateAndroidFingerprint(t *testing.T) {
	// These tests do not use t.Parallel: the temporary cwd is process-wide.
	previous, err := os.Getwd()
	if err != nil {
		t.Fatal(err)
	}
	root := t.TempDir()
	if err := os.Chdir(root); err != nil {
		t.Fatal(err)
	}
	defer os.Chdir(previous)
	if err := os.MkdirAll("ai/models", 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.Mkdir("mobile", 0700); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile("mobile/build.gradle.kts", []byte("code"), 0600); err != nil {
		t.Fatal(err)
	}
	model := "ai/models/best_float16.tflite"
	if err := os.WriteFile(model, []byte("model-v1"), 0600); err != nil {
		t.Fatal(err)
	}
	first, err := androidFingerprint()
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(model, []byte("model-v2"), 0600); err != nil {
		t.Fatal(err)
	}
	second, err := androidFingerprint()
	if err != nil {
		t.Fatal(err)
	}
	if first == second {
		t.Fatal("model changes must rebuild the APK")
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

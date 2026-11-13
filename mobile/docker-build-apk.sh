#!/bin/sh
# Runtime Android builder for the portable Compose demo. No host SDK is required.
set -eu
cd /workspace/mobile
mkdir -p /outputs
state() {
    printf '{"state":"%s"}\n' "$1" > /outputs/.build-status.tmp
    chmod 644 /outputs/.build-status.tmp
    mv /outputs/.build-status.tmp /outputs/build-status.json
}
trap 'state ERROR' EXIT
trap 'exit 143' TERM
trap 'exit 130' INT
state BUILDING
source_hash=$(
    { find . -type f ! -path './.gradle/*' ! -path './.kotlin/*' ! -path '*/build/*' ! -name local.properties -print | LC_ALL=C sort | xargs sha256sum; sha256sum /workspace/ai/models/best_float16.tflite; } | sha256sum | cut -d ' ' -f 1
)
if [ -f /outputs/source-sha256 ] && [ "$source_hash" = "$(cat /outputs/source-sha256)" ] &&
    [ -f /outputs/apk-sha256 ] && (cd /outputs && sha256sum -c apk-sha256); then
    state READY
    trap - EXIT
    echo 'APK не изменился: используем готовый файл.'
    exit 0
fi
if [ ! -f "$ANDROID_HOME/.iv-sdk-ready-v1" ]; then
    echo 'Подготовка Android SDK: первая загрузка может занять несколько минут.'
    if [ ! -x "$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager" ]; then
        curl --retry 3 -fsSL https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip -o /tmp/sdk.zip
        echo '4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583  /tmp/sdk.zip' | sha256sum -c -
        mkdir -p "$ANDROID_HOME/cmdline-tools"
        unzip -qo /tmp/sdk.zip -d "$ANDROID_HOME/cmdline-tools"
        mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest"
        rm /tmp/sdk.zip
    fi
    yes | sdkmanager --sdk_root="$ANDROID_HOME" 'platforms;android-37.0' 'build-tools;36.0.0' 'platform-tools'
    touch "$ANDROID_HOME/.iv-sdk-ready-v1"
fi
echo 'Android SDK готов. Сборка APK через Gradle; при первом запуске загружаются зависимости.'
sh gradlew :app:assembleDebug --no-daemon --build-cache --max-workers=4
"$ANDROID_HOME/build-tools/36.0.0/apksigner" verify app/build/outputs/apk/debug/app-debug.apk
cp app/build/outputs/apk/debug/app-debug.apk /outputs/.app-debug.apk.tmp
chmod 644 /outputs/.app-debug.apk.tmp
mv /outputs/.app-debug.apk.tmp /outputs/app-debug.apk
(cd /outputs && sha256sum app-debug.apk > apk-sha256)
printf '%s\n' "$source_hash" > /outputs/source-sha256
state READY
trap - EXIT
echo 'APK готов: /industrial-vision/android.apk'

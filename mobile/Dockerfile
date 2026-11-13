# syntax=docker/dockerfile:1
FROM eclipse-temurin:25-jdk AS tools
ENV ANDROID_HOME=/opt/android-sdk
ENV PATH="${ANDROID_HOME}/cmdline-tools/latest/bin:${PATH}"
RUN apt-get update && apt-get install -y --no-install-recommends curl unzip && rm -rf /var/lib/apt/lists/*

# Compose starts this target immediately; SDK/Gradle downloads happen in the background.
FROM tools AS runtime
WORKDIR /workspace/mobile
COPY mobile/ .
COPY ai/models/ /workspace/ai/models/
RUN chmod +x docker-build-apk.sh
ENTRYPOINT ["/bin/sh", "/workspace/mobile/docker-build-apk.sh"]

FROM tools AS builder
RUN curl -fsSL https://dl.google.com/android/repository/commandlinetools-linux-15859902_latest.zip -o /tmp/sdk.zip \
    && echo '4e4c464f145a7512b57d088ac6c278c03c9eea610886b35a5e0804e74eedf583  /tmp/sdk.zip' | sha256sum -c - \
    && mkdir -p "$ANDROID_HOME/cmdline-tools" \
    && unzip -q /tmp/sdk.zip -d "$ANDROID_HOME/cmdline-tools" \
    && mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" \
    && rm /tmp/sdk.zip
RUN yes | sdkmanager --sdk_root="$ANDROID_HOME" 'platforms;android-37.0' 'build-tools;36.0.0' 'platform-tools'
WORKDIR /workspace/mobile
COPY mobile/ .
COPY ai/models/ /workspace/ai/models/
RUN --mount=type=cache,id=industrial-vision-gradle,target=/root/.gradle,sharing=locked \
    --mount=type=cache,id=industrial-vision-android-signing,target=/root/.android,sharing=locked \
    --mount=type=cache,id=industrial-vision-project,target=/workspace/mobile/.gradle,sharing=locked \
    sh gradlew :app:assembleDebug --no-daemon --build-cache --max-workers=4 \
    && "$ANDROID_HOME/build-tools/36.0.0/apksigner" verify app/build/outputs/apk/debug/app-debug.apk
FROM scratch AS artifact
COPY --from=builder /workspace/mobile/app/build/outputs/apk/debug/app-debug.apk /app-debug.apk

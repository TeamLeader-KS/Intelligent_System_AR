FROM industrial-vision-demo-android:local
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
    libasound2t64 libdbus-1-3 libegl1 libfontconfig1 libgl1 libnss3 libpulse0 \
    libvulkan1 libx11-6 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
    libxext6 libxfixes3 libxi6 libxkbcommon0 libxrandr2 libxrender1 libxtst6 \
    python3 procps zip && rm -rf /var/lib/apt/lists/*
ENTRYPOINT []
CMD ["/bin/bash"]

CONFIGS = {
    "iso-base": {},
    # upstream's geckoview-isolated-process test variant (bug 1988531 part 1,
    # taskcluster/test_configs/variants.yml, landed 2026-10-06 for 159)
    "iso-rdd": {
        "media.android-media-codec.enabled": False,
        "media.android-media-codec.preferred": False,
        "media.ffmpeg.encoder.enabled": True,
        "media.ffvpx-hw.enabled": True,
        "media.rdd-ffvpx.enabled": True,
        "media.rdd-opus.enabled": True,
        "media.rdd-process.enabled": True,
        "media.rdd-vorbis.enabled": True,
        "media.rdd-vpx.enabled": True,
        "media.rdd-wav.enabled": True,
        "media.use-remote-encoder.video.platform": True,
    },
    # GPU-process variant: NDK MediaCodec via ffvpx in the GPU process,
    # AAC via the Java module in the utility process
    "iso-gpu": {
        "media.gpu-process-decoder": True,
        "media.ffvpx-hw.enabled": True,
        "media.utility-android-media-codec.enabled": True,
    },
}

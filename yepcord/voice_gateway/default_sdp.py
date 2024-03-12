DEFAULT_SDP = {
    "version": 0,
    "streams": [],
    "medias": [
        {
            "id": "0",
            "type": "audio",
            "direction": "sendrecv",
            "codecs": [
                {
                    "codec": "opus",
                    "type": 111,
                    "channels": 2,
                    "params": {
                        "minptime": "10",
                        "useinbandfec": "1"
                    },
                    "rtcpfbs": [
                        {
                            "id": "transport-cc"
                        }
                    ]
                }
            ],
            "extensions": {
                "1": "urn:ietf:params:rtp-hdrext:ssrc-audio-level",
                "2": "http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time",
                "3": "http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01",
                "4": "urn:ietf:params:rtp-hdrext:sdes:mid"
            }
        },
        {
            "id": "1",
            "type": "video",
            "direction": "sendrecv",
            "codecs": [
                {
                    "codec": "VP8",
                    "type": 96,
                    "rtx": 97,
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "VP9",
                    "type": 98,
                    "rtx": 99,
                    "params": {
                        "profile-id": "0"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "VP9",
                    "type": 100,
                    "rtx": 101,
                    "params": {
                        "profile-id": "2"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "VP9",
                    "type": 102,
                    "rtx": 122,
                    "params": {
                        "profile-id": "1"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 127,
                    "rtx": 121,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": "42001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 125,
                    "rtx": 107,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "0",
                        "profile-level-id": "42001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 108,
                    "rtx": 109,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": "42e01f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 124,
                    "rtx": 120,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "0",
                        "profile-level-id": "42e01f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 123,
                    "rtx": 119,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": "4d001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 35,
                    "rtx": 36,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "0",
                        "profile-level-id": "4d001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 37,
                    "rtx": 38,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": "f4001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 39,
                    "rtx": 40,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "0",
                        "profile-level-id": "f4001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                },
                {
                    "codec": "H264",
                    "type": 114,
                    "rtx": 115,
                    "params": {
                        "level-asymmetry-allowed": "1",
                        "packetization-mode": "1",
                        "profile-level-id": "64001f"
                    },
                    "rtcpfbs": [
                        {
                            "id": "goog-remb"
                        },
                        {
                            "id": "transport-cc"
                        },
                        {
                            "id": "ccm",
                            "params": ["fir"]
                        },
                        {
                            "id": "nack"
                        },
                        {
                            "id": "nack",
                            "params": ["pli"]
                        }
                    ]
                }
            ],
            "extensions": {
                "2": "http://www.webrtc.org/experiments/rtp-hdrext/abs-send-time",
                "3": "http://www.ietf.org/id/draft-holmer-rmcat-transport-wide-cc-extensions-01",
                "4": "urn:ietf:params:rtp-hdrext:sdes:mid",
                "5": "http://www.webrtc.org/experiments/rtp-hdrext/playout-delay",
                "6": "http://www.webrtc.org/experiments/rtp-hdrext/video-content-type",
                "7": "http://www.webrtc.org/experiments/rtp-hdrext/video-timing",
                "8": "http://www.webrtc.org/experiments/rtp-hdrext/color-space",
                "10": "urn:ietf:params:rtp-hdrext:sdes:rtp-stream-id",
                "11": "urn:ietf:params:rtp-hdrext:sdes:repaired-rtp-stream-id",
                "13": "urn:3gpp:video-orientation",
                "14": "urn:ietf:params:rtp-hdrext:toffset"
            }
        }
    ],
    "candidates": []
}

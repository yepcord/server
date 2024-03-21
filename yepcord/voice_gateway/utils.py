from typing import Optional

from semanticsdp import MediaInfo, SDPInfo


def get_sdp_media(sdp: SDPInfo, media_type: str) -> Optional[MediaInfo]:
    for media in sdp.medias:
        if media.type == media_type:
            return media


def _to_properties(media: MediaInfo, props: dict) -> None:
    if not media:
        return

    props[f"{media.type}.codecs.length"] = str(len(media.codecs))
    props[f"{media.type}.ext.length"] = str(len(media.extensions))

    for idx, codec in enumerate(media.codecs.values()):
        item = f"{media.type}.codecs.{idx}"
        props[f"{item}.codec"] = str(codec.codec)
        props[f"{item}.pt"] = str(codec.type)
        if codec.rtx:
            props[f"{item}.rtx"] = str(codec.rtx)

    for idx, (ext_id, ext_uri) in enumerate(media.extensions.items()):
        props[f"{media.type}.ext.{idx}.id"] = str(ext_id)
        props[f"{media.type}.ext.{idx}.uri"] = str(ext_uri)


def convert_rtp_properties(sdp: SDPInfo) -> dict:
    audio = get_sdp_media(sdp, "audio")
    video = get_sdp_media(sdp, "video")

    props = {}

    _to_properties(audio, props)
    _to_properties(video, props)

    return props

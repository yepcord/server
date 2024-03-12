from httpx import Request, Response

from yepcord.yepcord.utils import b64decode


def github_oauth_token_exchange(client_id: str, client_secret: str, code: str, access_token: str):
    def _github_oauth_token_exchange(request: Request) -> Response:
        params = request.url.params
        if params["client_id"] != client_id or params["client_secret"] != client_secret or params["code"] != code:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={"access_token": access_token})

    return _github_oauth_token_exchange


def github_oauth_user_get(access_token: str):
    def _github_oauth_user_get(request: Request) -> Response:
        if request.headers["Authorization"] != f"Bearer {access_token}":
            return Response(status_code=401, json={"error": ""})

        return Response(status_code=200, json={"id": str(int(f"0x{access_token[:6]}", 16)), "login": access_token[:8]})

    return _github_oauth_user_get


def reddit_oauth_token_exchange(client_id: str, client_secret: str, code: str, access_token: str):
    def _reddit_oauth_token_exchange(request: Request) -> Response:
        params = {k: v for k, v in [param.split("=") for param in request.content.decode("utf8").split("&")]}
        client_id_, client_secret_ = b64decode(request.headers["Authorization"][6:]).decode("utf8").split(":")
        if params["code"] != code or client_id_ != client_id or client_secret_ != client_secret:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={"access_token": access_token})

    return _reddit_oauth_token_exchange


def reddit_oauth_user_get(access_token: str):
    def _reddit_oauth_user_get(request: Request) -> Response:
        if request.headers["Authorization"] != f"Bearer {access_token}":
            return Response(status_code=401, json={"error": ""})

        return Response(status_code=200, json={"id": str(int(f"0x{access_token[:6]}", 16)), "name": access_token[:8]})

    return _reddit_oauth_user_get


def twitch_oauth_token_exchange(client_id: str, client_secret: str, code: str, access_token: str):
    def _twitch_oauth_token_exchange(request: Request) -> Response:
        params = {k: v for k, v in [param.split("=") for param in request.content.decode("utf8").split("&")]}
        if params["code"] != code or params["client_id"] != client_id or params["client_secret"] != client_secret:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={"access_token": access_token})

    return _twitch_oauth_token_exchange


def twitch_oauth_user_get(access_token: str):
    def _twitch_oauth_user_get(request: Request) -> Response:
        if request.headers["Authorization"] != f"Bearer {access_token}":
            return Response(status_code=401, json={"error": ""})

        return Response(status_code=200, json={"data": [
            {"id": str(int(f"0x{access_token[:6]}", 16)), "login": access_token[:8]}
        ]})

    return _twitch_oauth_user_get


def spotify_oauth_token_exchange(client_id: str, client_secret: str, code: str, access_token: str):
    def _spotify_oauth_token_exchange(request: Request) -> Response:
        params = {k: v for k, v in [param.split("=") for param in request.content.decode("utf8").split("&")]}
        client_id_, client_secret_ = b64decode(request.headers["Authorization"][6:]).decode("utf8").split(":")
        if params["code"] != code or client_id_ != client_id or client_secret_ != client_secret:
            return Response(status_code=400, json={"error": ""})

        return Response(status_code=200, json={"access_token": access_token})

    return _spotify_oauth_token_exchange


def spotify_oauth_user_get(access_token: str):
    def _spotify_oauth_user_get(request: Request) -> Response:
        if request.headers["Authorization"] != f"Bearer {access_token}":
            return Response(status_code=401, json={"error": ""})

        return Response(status_code=200, json={"id": str(int(f"0x{access_token[:6]}", 16)),
                                               "display_name": access_token[:8]})

    return _spotify_oauth_user_get

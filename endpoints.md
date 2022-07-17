# POST /api/v\*/auth/register
```json
{
  "fingerprint": "<id>.mjFS7rlHsybJJ1TpiEpmDhtI35o",
  "email": "<email>",
  "username": "<login>",
  "password": "<password>",
  "invite": null,
  "consent": true,
  "date_of_birth": "<YYYY-MM-DD>",
  "gift_code_sku_id": null,
  "captcha_key": null,
  "promotional_email_opt_in": false
}
```
```json
{
  "token": "<token>"
}
```

# POST api/v\*/auth/login
```json
{
  "login": "<login>",
  "password": "<password>",
  "undelete": false,
  "captcha_key": null,
  "login_source": null,
  "gift_code_sku_id": null
}
```
```json
{
  "token": "<token>",
  "user_settings": {
    "locale": "<locale>",
    "theme": "<theme>"
  },
  "user_id": "<id>"
}
```

# GET api/v\*/channels/<channel>
```json
{
  "id": "<channel>",
  "type": 1,
  "last_message_id": "<last_message>",
  "recipients": [{
    "id": "<u2_id>",
    "username": "<u2_login>",
    "avatar": "<u2_avatarhash>",
    "avatar_decoration": null,
    "discriminator": "<u2_discriminator>",
    "public_flags": 128
  }]
}
```
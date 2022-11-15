# YEPcord server
Unofficial discord server implementation in python.

# Setup
**Requirements:**
 - Python 3.9+
 - MariaDB database
 
**Setup**:
  1. Clone yepcord repository:
  ```bash
  git clone https://github.com/yepcord/server
  cd server
  ```
  2. Set environment variables:<br>
    `DB_HOST` - database host<br>
    `DB_USER` - database user<br>
    `DB_PASS` - database password<br>
    `DB_NAME` - database name<br>
    Optional variables:
     1. `STORAGE_TYPE` - file storage type (local/S3, default is local)<br>
         If storage type is local, optionally set `STORAGE_PATH` variable.<br>
         If storage type is s3, set `S3_ENDPOINT`, `S3_KEYID`, `S3_ACCESSKEY`, `S3_BUCKET` variables.
  3. Run: 
  ```bash
  python3 run_all.py
  ```
In production, you must also set `KEY` (random 16 bytes encoded in base64), `DOMAIN` and `PUBLIC_DOMAIN` environment variables.
# YEPcord server
Unofficial discord server implementation in python.

### For now I ([RuslanUC](https://github.com/RuslanUC)) don't have enough time to support YepCord (and lately not so much desire due to recent Discord actions). But you can contribute to the development of YepCord by creating a fork, implementing a feature (or fixing a bug, adding tests, etc.) and creating a pull-request.

[![Stand With Ukraine](.github/banner-direct.svg)](https://stand-with-ukraine.pp.ua)

# Setup
> :warning: **Setup instructions are outdated**!

<details>
  <summary>Setup instructions</summary>

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
       1. `STORAGE_TYPE` - file storage type (local/S3/ftp, default is local)<br>
           If storage type is local, optionally set `STORAGE_PATH` variable.<br>
           If storage type is s3, set `S3_ENDPOINT`, `S3_KEYID`, `S3_ACCESSKEY`, `S3_BUCKET` variables.<br>
           If storage type is ftp, set `FTP_HOST`, `FTP_PORT` (default is 21), `FTP_USER`, `FTP_PASSWORD` variables.
    3. Run: 
    ```bash
    python3 run_all.py
    ```
  In production, you must also set `KEY` (random 16 bytes encoded in base64), `DOMAIN` and `PUBLIC_DOMAIN` environment variables.
  
</details>

### License

**Any commit before 10.04.2023 is also covered by this license.**

Copyright (C) 2023 RuslanUC

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU Affero General Public License as
published by the Free Software Foundation version 3 of the
License

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License
along with this program. If not, see https://www.gnu.org/licenses/agpl-3.0.de.html
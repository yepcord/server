# YEPcord server
Unofficial discord backend implementation in python.

[![Stand With Ukraine](.github/banner-direct.svg)](https://stand-with-ukraine.pp.ua)

# Setup
**Requirements:**
 - Python 3.9+
 - Poetry (Optional)
 
**Setup**:
1. Clone yepcord repository:
    ```bash
    git clone https://github.com/yepcord/server yepcord-server && cd yepcord-server
    ```
2. Install requirements:
    ```bash
    poetry install
    ```
3. (Optional) Install and start redis, mysql/mariadb.
4. (Optional) Fill config file (example in config.example.py) with your values.
5. Run (with your config): 
    ```bash
    poetry run yepcord migrate -c yepcord-config.py
    poetry run yepcord run_all -c yepcord-config.py
    ```
   Run (with default config): 
    ```bash
    poetry run yepcord migrate
    poetry run yepcord run_all
    ```
   
**Install as python package and run (simple method):**
1. Install yepcord-server from pypi:
    ```bash
    pip install yepcord-server
    ```
2. (Optional) Install and start redis, mysql/mariadb.
3. (Optional) Fill config file (example in config.example.py) with your values.
4. Run (with your config): 
    ```bash
    yepcord migrate -c yepcord-config.py
    yepcord run_all -c yepcord-config.py
    ```
   Run (with default config): 
    ```bash
    yepcord migrate
    yepcord run_all
    ```


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
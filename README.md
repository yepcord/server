# YEPcord server
Unofficial discord backend implementation in python.

[![Stand With Ukraine](.github/banner-direct.svg)](https://stand-with-ukraine.pp.ua)

# Setup
**Requirements:**
 - Python 3.9+
 - Poetry
 
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
4. Write your config variables into src/settings.py (you can also write it into src/settings_prod.py, it ignored by git).
5. Run: 
    ```bash
    poetry run quart migrate
    poetry run quart run_all
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
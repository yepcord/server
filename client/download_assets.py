import requests

def download(url):
  r = requests.get(url)
  with open(f"assets/{url.split('/')[-1]}", "wb") as f:
    f.write(r.content)
  print(f"{url.split('/')[-1]} downloaded!")

#download("https://discord.com/assets/")

download("https://discord.com/assets/7e5013a9afc1404b0b89d99aaec0b398.png")
download("https://discord.com/assets/4a1000a95b1aad334e98f9d15b9d0ec4.svg")
download("https://discord.com/assets/91dcabd038a2e07ea6fbe7ddb625ecfb.woff2")
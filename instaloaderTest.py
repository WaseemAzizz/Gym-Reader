import instaloader

# 1. Setup the "Loader"
L = instaloader.Instaloader(download_videos=False, save_metadata=False, download_comments=False)

# 2. Target the profile
profile_name = "westernrecuserstats"

try:
    # This downloads the LATEST post from the profile
    # It creates a folder named after the profile
    L.download_profile(profile_name, profile_pic=False, fast_update=True)
    print("Download successful! Now check the folder for the image.")
except Exception as e:
    print(f"Instagram blocked the request: {e}")
#!/usr/bin/env python3
"""
Simple Steam API Key Testing Script
Tests if your Steam API key is working correctly
"""

import requests
import json
import sys

def test_steam_api_key():
    # Get API key from user
    api_key = input("Enter your Steam API Key: ").strip()
    
    if not api_key:
        print("❌ No API key provided!")
        return False
    
    # Validate API key format (32 hex characters)
    if len(api_key) != 32:
        print("❌ Invalid API key format! Steam API keys should be 32 characters long.")
        return False
    
    try:
        int(api_key, 16)
    except ValueError:
        print("❌ Invalid API key format! Steam API keys should be hexadecimal.")
        return False
    
    print(f"🔍 Testing API key: {api_key[:8]}...{api_key[-8:]}")
    print()
    
    # Test 1: Get Steam user info
    test_steam_id = input("Enter your SteamID64 (17 digits): ").strip()
    if not (test_steam_id.isdigit() and len(test_steam_id) == 17):
        print("❌ Invalid SteamID64! It should be 17 digits (e.g. 7656119XXXXXXXXXX).")
        return False

    print("Test 1: Getting user info...")
    
    try:
        response = requests.get(
            f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/",
            params={
                "key": api_key,
                "steamids": test_steam_id
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data and "players" in data["response"] and data["response"]["players"]:
                player = data["response"]["players"][0]
                print(f"✅ User info retrieved successfully!")
                print(f"   Username: {player.get('personaname', 'Unknown')}")
                print(f"   Profile URL: {player.get('profileurl', 'Unknown')}")
            else:
                print("❌ No user data returned (user might be private)")
        elif response.status_code == 403:
            print("❌ API key is invalid or doesn't have permission!")
            return False
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    print()
    
    # Test 2: Get owned games
    print("Test 2: Getting owned games...")
    
    try:
        response = requests.get(
            f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/",
            params={
                "key": api_key,
                "steamid": test_steam_id,
                "include_appinfo": "1",
                "include_played_free_games": "1"
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "response" in data and "games" in data["response"]:
                game_count = data["response"]["game_count"]
                print(f"✅ Games retrieved successfully!")
                print(f"   Total games: {game_count}")
                
                if game_count > 0:
                    # Show a few games as examples
                    games = data["response"]["games"][:3]
                    print("   Sample games:")
                    for game in games:
                        print(f"     - {game.get('name', 'Unknown')} (ID: {game.get('appid', 'Unknown')})")
                        
            else:
                print("❌ No games data returned (profile might be private)")
        elif response.status_code == 403:
            print("❌ API key is invalid!")
            return False
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            return False
            
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
        return False
    
    print()
    
    # Test 3: Get achievements for a common game (Team Fortress 2)
    print("Test 3: Getting achievements for Team Fortress 2...")
    
    try:
        response = requests.get(
            f"https://api.steampowered.com/ISteamUserStats/GetPlayerAchievements/v1/",
            params={
                "key": api_key,
                "steamid": test_steam_id,
                "appid": "440"  # Team Fortress 2
            },
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if "playerstats" in data and "achievements" in data["playerstats"]:
                achievements = data["playerstats"]["achievements"]
                unlocked = sum(1 for ach in achievements if ach.get("achieved", 0))
                total = len(achievements)
                print(f"✅ Achievements retrieved successfully!")
                print(f"   TF2 achievements: {unlocked}/{total} unlocked")
            else:
                print("❌ No achievement data (game not owned or stats private)")
        elif response.status_code == 403:
            print("❌ API key is invalid!")
            return False
        else:
            print(f"❌ Request failed with status code: {response.status_code}")
            
    except requests.RequestException as e:
        print(f"❌ Network error: {e}")
    
    print()
    print("🎉 Steam API key test completed successfully!")
    print("Your API key is working and can access Steam data.")
    return True

def main():
    print("=" * 50)
    print("Steam API Key Tester")
    print("=" * 50)
    print()
    
    if not test_steam_api_key():
        print("\n❌ API key test failed!")
        sys.exit(1)
    
    print("\n✅ All tests passed! Your Steam API key is working correctly.")

if __name__ == "__main__":
    main()
# BEGINNER SETUP — START HERE

You do not need to know programming. Follow the steps in order.

## Part 1 — Make the Discord bot

1. Open the Discord Developer Portal: https://discord.com/developers/applications
2. Click **New Application**.
3. Name it something like `MySpace Top 8 Comments` and create it.
4. In the left menu click **Bot**.
5. Click **Reset Token** / **View Token** and copy the token somewhere temporary.
   - Treat this like a password.
   - Never paste it into Unity, Discord chat, or a public GitHub file.
6. Still on the Bot page, find **Privileged Gateway Intents**.
7. Turn **Message Content Intent** ON and save.

## Part 2 — Add the bot to your Discord server

1. In the Developer Portal open **OAuth2 → URL Generator** (or **Installation**, depending on the current Discord layout).
2. Select the `bot` scope.
3. Give the bot only these permissions:
   - **View Channels**
   - **Read Message History**
4. Open the generated install URL and add the bot to your server.
5. In Discord, make sure the bot can see the exact channel you want to use for MySpace comments.

The bot does NOT need Administrator, Send Messages, Manage Messages, or any other broad permission.

## Part 3 — Get the Discord channel ID

1. Discord → **User Settings → Advanced**.
2. Turn **Developer Mode** ON.
3. Right-click the channel that will become the MySpace comments section.
4. Click **Copy Channel ID**.
5. Keep that number handy.

## Part 4 — Create the free GitHub repository

1. Sign in at https://github.com/
2. Click **New repository**.
3. Name it something simple, for example `myspace-top8-comments`.
4. Make it **Public**. This keeps GitHub Pages/Actions simple and free; your bot token will still be stored privately as a GitHub secret.
5. Do NOT add a README, .gitignore, or license on the create screen.
6. Create the repository.

## Part 5 — Upload this repository folder

The ZIP you received contains a folder named `github-repo`.

1. Open your new GitHub repository in the browser.
2. Choose **Add file → Upload files**.
3. Drag the CONTENTS of the `github-repo` folder into the upload page.
   - You should see `.github`, `tools`, `site`, `README.md`, and `requirements.txt` at the repository root.
4. Commit the upload to the `main` branch.

If your browser refuses to upload the hidden `.github` folder, use GitHub Desktop instead, or create `.github/workflows/update-comments.yml` manually from the included file.

## Part 6 — Add the two GitHub secrets

1. In the GitHub repository open **Settings**.
2. Go to **Secrets and variables → Actions**.
3. Click **New repository secret**.
4. Create this secret:
   - Name: `DISCORD_BOT_TOKEN`
   - Value: the Discord bot token from Part 1
5. Create a second secret:
   - Name: `DISCORD_CHANNEL_ID`
   - Value: the channel ID from Part 3

That is the only private setup GitHub needs.

## Part 7 — Turn on GitHub Pages

1. Repository **Settings → Pages**.
2. Under **Build and deployment**, set **Source** to **GitHub Actions**.
3. Save if GitHub shows a Save button.

## Part 8 — Run it once immediately

You do not have to wait five minutes for the first run.

1. Open the repository's **Actions** tab.
2. Click **Update VRChat Comments** on the left.
3. Click **Run workflow → Run workflow**.
4. Open the running job and wait for it to finish with green checkmarks.
5. Go back to **Settings → Pages**. GitHub will show your public site address.

It will look like:

`https://YOUR-GITHUB-NAME.github.io/myspace-top8-comments/`

Open this in a browser:

`https://YOUR-GITHUB-NAME.github.io/myspace-top8-comments/comments.json`

You should see your latest Discord comments as text data.

Also test:

`https://YOUR-GITHUB-NAME.github.io/myspace-top8-comments/profile-photos-0.jpg`

One of profile-photos-0 through profile-photos-5 will contain the current eight Discord profile photos.

## Part 9 — Import the Unity package

1. Open your VRChat world project in Unity.
2. Double-click `MySpaceTop8_DiscordComments_UnityUI.unitypackage`.
3. Click **Import**.
4. Wait for Unity/UdonSharp to compile.

## Part 10 — Build the comments UI

1. Unity top menu → **Tools → MySpace Top 8 → Build Discord Comments UI**.
2. Paste your GitHub Pages base URL from Part 8.
   Example: `https://YOUR-GITHUB-NAME.github.io/myspace-top8-comments/`
3. Choose your **Refresh Interval Seconds**.
   - 300 = every 5 minutes.
   - GitHub itself checks Discord every 5 minutes, so checking more often usually will not show newer data sooner.
4. Click **Build Comments UI**.

Unity creates one editable World Space Canvas with eight normal Unity UI comment rows.

Each row contains:
- Discord profile photo = `RawImage`
- Discord display name = TextMeshPro
- timestamp = TextMeshPro
- Discord message = TextMeshPro

You can resize, recolor, move, restyle, or replace any of those UI objects normally.

## How updating behaves

The visible comments DO NOT update piece-by-piece.

Unity keeps the current comments visible while it fetches:
1. the new `comments.json`, and
2. the one atlas image containing all eight Discord profile photos.

When the atlas finishes, Unity updates every profile photo, name, timestamp, message, and active row in the same frame.

So visually it behaves like a webpage refresh: old page → new page.

## Update timing

There are two separate clocks:

- **GitHub/Discord sync:** every 5 minutes. GitHub's scheduler has a 5-minute minimum and can occasionally run a little late.
- **Unity refresh interval:** whatever you set on the `MySpaceDiscordComments` component.

For the simplest setup, use **300 seconds** for Unity too.

## If something does not work

### GitHub Action says 401
Your Discord bot token is wrong. Reset it in Discord Developer Portal and replace the GitHub secret.

### GitHub Action says 403
The bot cannot see/read that Discord channel. Give it View Channel + Read Message History for that channel.

### GitHub Action says 404
The channel ID is wrong, or the bot is not in that Discord server.

### comments.json works in browser but Unity stays blank
Check that the base URL in the Unity component ends with `/` and is the GitHub Pages URL, not the normal github.com repository URL.

### Messages have no content
Confirm **Message Content Intent** is enabled on the Discord bot page.

### Unity reports a remote image/string error
Use the `*.github.io` Pages URL. VRChat trusts GitHub Pages by default.

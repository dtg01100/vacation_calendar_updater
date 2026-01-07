# Vacation Calendar Updater

A tool for managing vacation calendar events in Google Calendar.

## Setup

### Google API Credentials

This application requires a `client_secret.json` file from Google Cloud Platform:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Create OAuth 2.0 credentials
5. Download the client_secret.json file

### Running the Application

#### From Source
```bash
./run.sh
```

#### From Flatpak
```bash
flatpak run com.github.dtg01100.vacation_calendar_updater
```

### Client Secret Location

The application looks for `client_secret.json` in the following locations:

- **Flatpak**: `~/.var/app/com.github.dtg01100.vacation_calendar_updater/config/`
- **Source**: The current working directory or `~/.config/vacation-calendar-updater/`

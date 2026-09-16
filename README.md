# Mammotion Plugin for PG3x / IoX

A PG3x node server for Mammotion robotic lawn equipment using the official Mammotion Developer API.

## Features

The plugin automatically discovers supported Mammotion devices and creates IoX nodes for them.

For Mammotion robotic mowers, currently available information includes:

- Mower status
- Battery level
- Charging status
- Online status
- Active network
- Wi-Fi signal strength
- Cellular signal strength

Supported mower commands include:

- Pause
- Resume
- Return to charger
- Cancel return
- Query

After a mower command, the plugin automatically refreshes mower status to account for delays in Mammotion cloud status updates.

## Configuration

This plugin requires Mammotion Developer API credentials.

Add the following Custom Parameters in PG3x:

- `client_id` - Mammotion Developer API Client ID
- `client_secret` - Mammotion Developer API Client Secret

Restart the plugin after entering the credentials.

## API Support

This plugin uses the official Mammotion Developer API.

Available functionality depends on the capabilities Mammotion exposes for each device model through the public API. Some real-time telemetry features, including detailed mowing progress, are not currently available through the public API for all mower models.

## Requirements

- PG3x
- IoX
- Internet connectivity
- Mammotion Developer API credentials

## Version

Current version: 1.0.1

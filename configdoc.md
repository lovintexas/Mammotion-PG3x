# Mammotion Configuration

This plugin uses the official Mammotion Developer API.

## Mammotion Developer Credentials

Obtain API credentials from the Mammotion Developer portal.

In the PG3x plugin configuration, add these Custom Parameters:

- `client_id` - Your Mammotion Developer API Client ID
- `client_secret` - Your Mammotion Developer API Client Secret

The parameter names must be entered exactly as shown above.

After entering both parameters, restart the Mammotion plugin.

The plugin will authenticate with Mammotion, discover supported devices associated with the developer account, and create the corresponding IoX nodes.

## Notes

The plugin currently provides the telemetry and commands available through the official Mammotion Developer API.

Some advanced real-time telemetry features are currently limited by Mammotion to supported mower models and may not be available for all devices.

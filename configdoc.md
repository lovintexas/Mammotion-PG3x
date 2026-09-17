# Mammotion Configuration

This plugin uses the official Mammotion Developer API.

## Mammotion Developer Credentials

This plugin requires credentials from the Mammotion Developer API.

1. Go to the Mammotion Developer Portal:

   https://developer.mammotion.com/credentials

2. Sign in with your Mammotion account.

3. Create a developer credential and save the Client ID and Client Secret.

4. In the PG3x Mammotion plugin configuration, enter your credentials in the pre-created Custom Parameters:

   - `client_id` - Your Mammotion Developer API Client ID
   - `client_secret` - Your Mammotion Developer API Client Secret

5. Restart the Mammotion plugin after entering the credentials.

## Notes

The plugin will authenticate with Mammotion, discover supported devices associated with the developer account, and create the corresponding IoX nodes.

The plugin currently provides the telemetry and commands available through the official Mammotion Developer API.

Some advanced real-time telemetry features are currently limited by Mammotion to supported mower models and may not be available for all devices.

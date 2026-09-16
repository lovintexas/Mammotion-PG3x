#!/usr/bin/env python3

import sys
import hashlib
import threading
import time
import os
import markdown2
import requests
import udi_interface

LOGGER = udi_interface.LOGGER
VERSION = "1.0.2"

AUTH_URL = "https://id.mammotion.com/oauth2/token"
API_BASE = "https://api-open.mammotion.com"

polyglot = udi_interface.Interface([])
controller = None
poll_lock = threading.Lock()


STATUS_MAP = {
    "Standby": 2,
    "Mowing": 3,
    "TaskPaused": 4,
    "Returning": 5,
    "Working": 3,
    "Paused": 4,
    "Mapping": 6,
    "Updating": 7,
    "Offline": 1,
    "Abnormal": 8,
}


class SpinoNode(udi_interface.Node):
    id = 'spino'

    drivers = [
        {'driver': 'GV3', 'value': 0, 'uom': 25},
    ]

    def __init__(
        self,
        polyglot,
        primary,
        address,
        name,
        device_id,
        model=None,
        version=None
    ):
        super().__init__(polyglot, primary, address, name)

        self.device_id = device_id
        self.model = model
        self.version = version

    def update_status(self):
        global controller

        if controller is None:
            return

        try:
            data = controller.get_device(self.device_id)

            if not data:
                LOGGER.warning(
                    f'No data returned for {self.name}'
                )
                return

            online = int(data.get('online') or 0)
            self.setDriver('GV3', online)

            LOGGER.info(
                f'{self.name}: online={online}'
            )

        except Exception as err:
            LOGGER.error(
                f'Error updating {self.name}: {err}'
            )

    def query(self, command=None):
        self.update_status()

    commands = {
        'QUERY': query,
    }


class MowerNode(udi_interface.Node):
    id = 'mower'

    drivers = [
        {'driver': 'ST',  'value': 0, 'uom': 25},
        {'driver': 'GV1', 'value': 0, 'uom': 51},
        {'driver': 'GV2', 'value': 0, 'uom': 25},
        {'driver': 'GV3', 'value': 0, 'uom': 25},
        {'driver': 'GV4', 'value': 0, 'uom': 25},
        {'driver': 'GV5', 'value': 0, 'uom': 56},
        {'driver': 'GV6', 'value': 0, 'uom': 56},
    ]

    def __init__(
        self,
        polyglot,
        primary,
        address,
        name,
        device_id,
        model=None,
        version=None
    ):
        super().__init__(polyglot, primary, address, name)

        self.device_id = device_id
        self.model = model
        self.version = version

    def update_status(self):
        global controller

        if controller is None:
            return

        try:
            data = controller.get_device(self.device_id)

            if not data:
                LOGGER.warning(
                    f'No data returned for {self.name}'
                )
                return

            online = int(data.get('online') or 0)
            self.setDriver('GV3', online)

            if not online:
                # Preserve last-known battery/RSSI values.
                self.setDriver('ST', 1)
                LOGGER.info(f'{self.name}: Offline')
                return

            raw_status = data.get('status')

            if raw_status is None:
                status_value = 0
            else:
                status_value = STATUS_MAP.get(raw_status, 0)

                if raw_status not in STATUS_MAP:
                    LOGGER.warning(
                        f'Unknown Mammotion status for '
                        f'{self.name}: {raw_status}'
                    )

            self.setDriver('ST', status_value)

            battery = data.get('batteryLevel')
            if battery is not None:
                self.setDriver('GV1', int(battery))

            charge = data.get('chargeStatus')
            if charge is not None:
                self.setDriver('GV2', 1 if int(charge) else 0)

            network = data.get('network') or {}

            used_network = network.get('usedNetwork')
            if used_network is not None:
                try:
                    self.setDriver('GV4', int(used_network))
                except (TypeError, ValueError):
                    self.setDriver('GV4', 0)

            wifi_rssi = network.get('wifiRssi')
            if wifi_rssi is not None:
                self.setDriver('GV5', int(wifi_rssi))

            cellular_rssi = network.get('cellularRssi')
            if cellular_rssi is not None:
                self.setDriver('GV6', int(cellular_rssi))

            LOGGER.info(
                f'{self.name}: '
                f'status={raw_status}, '
                f'battery={battery}, '
                f'charge={charge}, '
                f'online={online}'
            )

        except Exception as err:
            LOGGER.error(
                f'Error updating {self.name}: {err}'
            )

    def send_action(self, action):
        global controller

        if controller is None:
            return

        try:
            LOGGER.info(
                f'Sending {action} command to {self.name}'
            )

            result = controller.api_post(
                '/v1/mower/action',
                {
                    'deviceId': self.device_id,
                    'action': action
                }
            )

            LOGGER.info(
                f'{self.name} {action} result: {result}'
            )

            # Mammotion status may take a few seconds to update.
            def refresh():
                for delay in (3, 5, 7):
                    time.sleep(delay)
                    self.update_status()

            threading.Thread(
                target=refresh,
                daemon=True,
                name=f'MammotionRefresh-{self.address}'
            ).start()

        except Exception as err:
            LOGGER.error(
                f'Error sending {action} to {self.name}: {err}'
            )

    def pause(self, command=None):
        self.send_action('PAUSE')

    def resume(self, command=None):
        self.send_action('RESUME')

    def return_to_charger(self, command=None):
        self.send_action('RETURN')

    def cancel_return(self, command=None):
        self.send_action('CANCEL_RETURN')

    def query(self, command=None):
        self.update_status()

    commands = {
        'PAUSE': pause,
        'RESUME': resume,
        'RETURN': return_to_charger,
        'CANCEL_RETURN': cancel_return,
        'QUERY': query,
    }


class Controller(udi_interface.Node):
    id = 'mammotion'

    drivers = [
        {'driver': 'ST', 'value': 0, 'uom': 25},
    ]

    def __init__(self, polyglot, primary, address, name):
        super().__init__(
            polyglot,
            primary,
            address,
            name
        )

        self.client_id = None
        self.client_secret = None

        self.access_token = None
        self.token_expires_at = 0

        self.mowers = {}

        self.session = requests.Session()

    def configure(self, params):
        self.client_id = params.get('client_id')
        self.client_secret = params.get('client_secret')

        if not self.client_id or not self.client_secret:
            LOGGER.warning(
                'Please configure client_id and '
                'client_secret in PG3x.'
            )
            self.setDriver('ST', 0)
            return

        self.connect()

    def authenticate(self):
        LOGGER.info('Authenticating with Mammotion')

        response = self.session.post(
            AUTH_URL,
            headers={
                'Content-Type':
                'application/x-www-form-urlencoded'
            },
            data={
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'grant_type': 'client_credentials',
            },
            timeout=20
        )

        response.raise_for_status()

        result = response.json()

        if result.get('code') != 0:
            raise RuntimeError(
                f'Mammotion authentication failed: {result}'
            )

        data = result.get('data') or {}

        self.access_token = data.get('access_token')

        if not self.access_token:
            raise RuntimeError(
                'Mammotion returned no access token'
            )

        expires_in = int(data.get('expires_in') or 3600)

        # Refresh five minutes before expiration.
        self.token_expires_at = (
            time.time() + max(60, expires_in - 300)
        )

        LOGGER.info(
            f'Mammotion authentication successful; '
            f'token lifetime {expires_in} seconds'
        )

    def ensure_token(self):
        if (
            not self.access_token
            or time.time() >= self.token_expires_at
        ):
            self.authenticate()

    def api_get(self, path):
        self.ensure_token()

        response = self.session.get(
            f'{API_BASE}{path}',
            headers={
                'Authorization':
                f'Bearer {self.access_token}'
            },
            timeout=20
        )

        # If Mammotion rejects the token unexpectedly,
        # authenticate once and retry.
        if response.status_code in (401, 403):
            LOGGER.warning(
                'Mammotion token rejected; '
                're-authenticating'
            )

            self.authenticate()

            response = self.session.get(
                f'{API_BASE}{path}',
                headers={
                    'Authorization':
                    f'Bearer {self.access_token}'
                },
                timeout=20
            )

        response.raise_for_status()

        result = response.json()

        if result.get('code') != 0:
            raise RuntimeError(
                f'Mammotion API error: {result}'
            )

        return result.get('data')

    def api_post(self, path, payload):
        self.ensure_token()

        response = self.session.post(
            f'{API_BASE}{path}',
            headers={
                'Authorization':
                f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            },
            json=payload,
            timeout=20
        )

        if response.status_code in (401, 403):
            LOGGER.warning(
                'Mammotion token rejected; '
                're-authenticating'
            )

            self.authenticate()

            response = self.session.post(
                f'{API_BASE}{path}',
                headers={
                    'Authorization':
                    f'Bearer {self.access_token}',
                    'Content-Type': 'application/json'
                },
                json=payload,
                timeout=20
            )

        response.raise_for_status()

        result = response.json()

        if result.get('code') != 0:
            raise RuntimeError(
                f'Mammotion API error: {result}'
            )

        data = result.get('data') or {}

        if data.get('commandResult') is False:
            raise RuntimeError(
                f'Mammotion command failed: '
                f'{data.get("resultMessage")}'
            )

        return data

    def get_device(self, device_id):
        return self.api_get(
            f'/v1/mower/{device_id}'
        )

    def connect(self):
        try:
            self.authenticate()
            self.discover_devices()
            self.setDriver('ST', 1)

        except Exception as err:
            LOGGER.error(
                f'Mammotion connection failed: {err}'
            )
            self.setDriver('ST', 0)

    def discover_devices(self):
        devices = self.api_get('/v1/mowers') or []

        LOGGER.info(
            f'Mammotion returned {len(devices)} device(s)'
        )

        for device in devices:
            device_id = device.get('id')
            model = device.get('model') or ''
            name = device.get('name') or model or 'Mammotion'

            if not device_id:
                continue

            # RTK stations are returned by /v1/mowers,
            # but are not mower nodes.
            if model.upper().startswith('RTK'):
                LOGGER.info(
                    f'Ignoring RTK device: '
                    f'{name} ({model})'
                )
                continue

            address = 'm' + hashlib.md5(
                device_id.encode()
            ).hexdigest()[:10]

            if address in self.mowers:
                continue

            detail = None

            try:
                detail = self.get_device(device_id)
            except Exception as err:
                LOGGER.warning(
                    f'Could not retrieve initial detail '
                    f'for {name}: {err}'
                )

            detail = detail or {}

            final_model = detail.get('model') or model

            if final_model.upper().startswith('SPINO'):
                node_class = SpinoNode
            else:
                node_class = MowerNode

            node = node_class(
                polyglot,
                self.address,
                address,
                name,
                device_id,
                model=final_model,
                version=detail.get('version')
            )

            self.mowers[address] = node
            polyglot.addNode(node)

            LOGGER.info(
                f'Added device {name} '
                f'({model}) as {address}'
            )

            node.update_status()

    def query(self, command=None):
        if not self.client_id or not self.client_secret:
            return

        try:
            self.ensure_token()
            self.setDriver('ST', 1)
        except Exception as err:
            LOGGER.error(
                f'Mammotion authentication error: {err}'
            )
            self.setDriver('ST', 0)
            return

        for node in self.mowers.values():
            node.update_status()

    commands = {
        'QUERY': query,
    }


def custom_params_handler(params):
    global controller

    LOGGER.info('Received custom parameters')

    if controller is None:
        controller = Controller(
            polyglot,
            'controller',
            'controller',
            'Mammotion Controller'
        )

        polyglot.addNode(controller)

    controller.configure(params)


def poll_handler(poll_type):
    if controller is None:
        return

    if poll_type != 'shortPoll':
        return

    if not poll_lock.acquire(blocking=False):
        LOGGER.warning(
            'Previous Mammotion poll still running; '
            'skipping this poll'
        )
        return

    try:
        controller.query()
    finally:
        poll_lock.release()


def stop_handler():
    LOGGER.info('Mammotion plugin stopping')
    polyglot.stop()


if __name__ == '__main__':
    try:
        polyglot.start(VERSION)

        polyglot.subscribe(
            polyglot.CUSTOMPARAMS,
            custom_params_handler
        )

        polyglot.subscribe(
            polyglot.POLL,
            poll_handler
        )

        polyglot.subscribe(
            polyglot.STOP,
            stop_handler
        )

        configuration_help = './configdoc.md'

        if os.path.isfile(configuration_help):
            cfgdoc = markdown2.markdown_path(
                configuration_help
            )
            polyglot.setCustomParamsDoc(cfgdoc)

        polyglot.ready()
        polyglot.updateProfile()

        polyglot.runForever()

    except (KeyboardInterrupt, SystemExit):
        sys.exit(0)

    except Exception:
        LOGGER.exception('Unhandled exception')
        polyglot.stop()
        sys.exit(1)

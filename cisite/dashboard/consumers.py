"""
SPDX-License-Identifier: BSD-3-Clause
Developed by UNH-IOL dpdklab@iol.unh.edu.
"""

from channels.generic.websocket import AsyncWebsocketConsumer
import json


class ManageEnvironmentConsumer(AsyncWebsocketConsumer):
    """This is a push based (instead of polling) progress bar"""
    # environment: { current: value, total: value }
    current = {}

    async def connect(self):
        await self.accept()
        await self.clear()

        await self.channel_layer.group_add(
            'manage-environment',
            self.channel_name
        )

        await self._send_update()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'manage-environment',
            self.channel_name
        )

        await self.clear()

    async def clear(self):
        """If any environments are at 100%, delete them"""
        for env in [env for env in self.current if self.current[env]['total'] == self.current[env]['current']]:
            del self.current[env]

    async def _send_update(self):
        await self.send(text_data=json.dumps({
            'type': 'current',
            'message': self.current
        }))

    async def update_current(self, event):
        self.current[event['environment']] = event['message']
        await self._send_update()

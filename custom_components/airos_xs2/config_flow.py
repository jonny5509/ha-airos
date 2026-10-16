import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN
from .device import normalize_device_metadata


class AiRXS2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            # Some legacy airOS devices return their identity as a comma-separated
            # UBNT metadata string. Never use that entire string as the device name.
            metadata = normalize_device_metadata(user_input["name"])
            data = {
                **user_input,
                **{
                    key: value
                    for key, value in metadata.items()
                    if value is not None
                },
            }
            return self.async_create_entry(
                title=metadata["name"],
                data=data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required("name"): str,
                    vol.Required("host"): str,
                    vol.Required("username"): str,
                    vol.Required("password"): str,
                }
            ),
        )

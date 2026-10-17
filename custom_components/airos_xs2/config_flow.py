import voluptuous as vol
from homeassistant import config_entries

from .const import DOMAIN


class AiRXS2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the AirOS integration setup."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Show the AirOS connection form and create the config entry."""
        if user_input is not None:
            host = user_input["host"].strip()
            name = user_input["name"].strip()
            if not host:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._data_schema(),
                    errors={"host": "required"},
                )

            # Avoid duplicate polling and unique-ID collisions for the same host,
            # including entries created by older versions without a config-flow ID.
            if any(
                str(existing.data.get("host", "")).strip().casefold() == host.casefold()
                for existing in self._async_current_entries()
            ):
                return self.async_abort(reason="already_configured")

            await self.async_set_unique_id(host.casefold())
            self._abort_if_unique_id_configured()

            data = dict(user_input)
            data["host"] = host
            data["name"] = name or host
            return self.async_create_entry(
                title=data["name"],
                data=data,
            )

        return self.async_show_form(
            step_id="user",
            data_schema=self._data_schema(),
        )

    @staticmethod
    def _data_schema():
        """Build the form schema and reject empty connection fields."""
        non_empty = vol.All(str, vol.Length(min=1))
        return vol.Schema(
            {
                vol.Required("name"): str,
                vol.Required("host"): non_empty,
                vol.Required("username"): non_empty,
                vol.Required("password"): non_empty,
            }
        )

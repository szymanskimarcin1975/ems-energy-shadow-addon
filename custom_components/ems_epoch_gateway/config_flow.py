"""One-step setup; creates no authorization or hardware connection."""
from homeassistant import config_entries

DOMAIN = "ems_epoch_gateway"


class EMSEpochGatewayConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()
        if user_input is not None:
            return self.async_create_entry(title="EMS Epoch Gateway (safe / read-only)", data={})
        return self.async_show_form(step_id="user")

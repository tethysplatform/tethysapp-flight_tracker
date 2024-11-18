from tethys_sdk.base import TethysAppBase
from tethys_sdk.app_settings import CustomSetting


class FlightTracker(TethysAppBase):
    """
    Tethys app class for Flight Tracker.
    """

    name = 'Flight Tracker'
    description = ''
    package = 'flight_tracker'  # WARNING: Do not change this value
    index = 'home'
    icon = f'{package}/images/airplane-icon.png'
    root_url = 'flight-tracker'
    color = '#f39c12'
    tags = ''
    enable_feedback = False
    feedback_emails = []

    def custom_settings(self):
        custom_settings = (
            CustomSetting(
                name='cesium_ion_token',
                type=CustomSetting.TYPE_STRING,
                description='Cesium Ion Access Token',
                required=True                
            ),
            CustomSetting(
                name='open_sky_username',
                type=CustomSetting.TYPE_STRING,
                description='OpenSky network username for API access',
                required=True
            ),
            CustomSetting(
                name='open_sky_password',
                type=CustomSetting.TYPE_STRING,
                description='OpenSky network password for API access',
                required=True
            ),
        )

        return custom_settings
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
                name='opensky_api_client_id',
                type=CustomSetting.TYPE_STRING,
                description='OpenSky Network API Client ID',
                required=False,
            ),
            CustomSetting(
                name='opensky_api_client_secret',
                type=CustomSetting.TYPE_STRING,
                description='OpenSky Network Client Secret',
                required=False,
            )
        )

        return custom_settings
from default_config import DefaultConfig
from globals import TEST_DATABASE_URI

class ConfigTest(DefaultConfig):
    
    def __init__(self) -> None:
        super().__init__()
        self.database_uri = TEST_DATABASE_URI
        
def getUrl(*url) -> str:
    return f"{config_test.api_prefix}/{'/'.join(url)}"

config_test = ConfigTest()
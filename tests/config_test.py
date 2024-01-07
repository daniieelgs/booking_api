import traceback
from access import Access
from default_config import DefaultConfig
from globals import ADMIN_ROLE, CANCELLED_STATUS, CONFIRMED_STATUS, DONE_STATUS, LOCAL_ROLE, PENDING_STATUS, TEST_DATABASE_URI, USER_ROLE, WEEK_DAYS
from models.status import StatusModel
from models.user_session import UserSessionModel
from app import db as default_db
from models.weekday import WeekdayModel

class ConfigTest(DefaultConfig):
    
    def __init__(self) -> None:
        super().__init__()
        self.database_uri = TEST_DATABASE_URI
        self.waiter_booking_status = None
       
    def insertUserSession(self, db):
        
        data = [
            {
                "user": ADMIN_ROLE,
                "name": "Admin"
            },
            {
                "user": LOCAL_ROLE,
                "name": "Local"
            },
            {
                "user": USER_ROLE,
                "name": "User"
            }
        ]

        id = 1
        for d in data:
            model = UserSessionModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise
        
    def insertStatus(self, db):
        data = [
            {
                "status": PENDING_STATUS,
                "name": "Pending"
            },
            {
                "status": CONFIRMED_STATUS,
                "name": "Confirmed"
            },
            {
                "status": DONE_STATUS,
                "name": "Done"
            },
            {
                "status": CANCELLED_STATUS,
                "name": "Cancelled"
            }
        ]

        id = 1
        for d in data:
            model = StatusModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise
        
    def insertWeekdays(self, db):
        
        name_weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        
        data = []
        
        for i in range(len(WEEK_DAYS)):
            data.append({
                "weekday": WEEK_DAYS[i],
                "name": name_weekdays[i]
            })

        id = 1
        for d in data:
            model = WeekdayModel(id=id, **d)
            db.session.add(model)

            id += 1
          
        try:
            db.session.commit()
        except:
            traceback.print_exc()
            db.session.rollback()
            raise

    def createAdminToken(self, db):
        access = Access(db_sqlite='instance/' + config_test.database_uri.split('///')[-1])
        
        db = access.connectToDB()

        self.ADMIN_TOKEN = access.makeToken(db, 1, copy_on_clipboard = False)

    def config(self, *args, **kwargs):
        super().config(*args, **kwargs)
        
        db = kwargs['db']
        
        print("Configuring database tests...")
        db = db or default_db
        print(db)
        
        self.insertUserSession(db)
        self.insertStatus(db)
        self.insertWeekdays(db)
        
        self.createAdminToken(db)

        
        
def getUrl(*url) -> str:
    return f"{config_test.api_prefix}/{'/'.join([str(u) for u in url])}"

def setParams(url, **params) -> str:
    return f"{url}?{'&'.join([f'{param}={params[param]}' for param in params])}"

config_test = ConfigTest()
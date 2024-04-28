import datetime
import elapsed_time

'''Static Record of a Zone - used to define a zone and the command to run it'''
class ZoneRecord:

    def __init__(self, zone_name : str,
                 mqtt_command : str,
                 default_run_time_seconds : int = 300):
        self.zone_name = zone_name
        self.mqtt_command = mqtt_command
        self.default_run_time_seconds = default_run_time_seconds

'''A Zone command and state of the command'''
class ZoneCommand:
    
    '''Private Class Members'''
    _elapsed_timer = None
    _active = False

    def __init__(self, zone : ZoneRecord, run_time : datetime.timedelta):
        self.zone = zone
        self._run_time = run_time
    
    def start(self):
        self._elapsed_timer = elapsed_time.ElapsedTime(self._run_time)
        self._active = True
    
    def is_elapsed(self) -> bool:
        return self._elapsed_timer.is_elapsed()
    
    def remaining_time(self) -> datetime.timedelta:
        return self._elapsed_timer.remaining_time()
    
    def is_active(self) -> bool:
        return self._active
     
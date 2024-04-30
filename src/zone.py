import datetime
import elapsed_time
import jsonpickle

'''Static Record of a Zone - used to define a zone and the command to run it'''
class ZoneRecord():
    
    def __init__(self):
        self.zone_name = None
        self.mqtt_command = None
        self.zone_index = 0
        self.run_time_seconds = 0
        
def CreateZoneRecord(zone_name : str, zone_index : int, mqtt_command : str, run_time_seconds : int):
    zone = ZoneRecord()
    zone.zone_name = zone_name
    zone.zone_index = zone_index
    zone.mqtt_command = mqtt_command
    zone.run_time_seconds = run_time_seconds
    return zone

'''A Zone command and state of the command'''
class ZoneCommand:
    
    '''Private Class Members'''
    _elapsed_timer = None
    _active = False

    def __init__(self, zone : ZoneRecord, run_time : datetime.timedelta):
        self.zone = zone
        self.run_time = run_time
    
    def start(self):
        self._elapsed_timer = elapsed_time.ElapsedTime(self.run_time)
        self._active = True
    
    def is_elapsed(self) -> bool:
        return self._elapsed_timer.is_elapsed()
    
    def remaining_time(self) -> datetime.timedelta:
        return self._elapsed_timer.remaining_time()
    
    def is_active(self) -> bool:
        return self._active

if __name__ == "__main__":
    zone = ZoneRecord()
    print(jsonpickle.encode(zone, unpicklable=False))
     
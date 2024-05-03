import time
import datetime
import json
import jsonpickle
from collections import defaultdict

import logger
import controller_config
import mqtt_client_pubsub
import command_queue
import zone
import elapsed_time

'''
The Irrigation Controller subscribes to MQTT and awaits commands to run irrigation zones.
The app enforces certain rules to prevent overwatering and to ensure that the system is not running when it should not be.

MQTT Subscriptions:
command_queue - The command queue is used to send commands to the irrigation controller.

MQTT Publishes:
command_status - contains a list of the queued commands and the current running time for each command.

'''
class IrrigationController:
    
    # Private Class Constants
    _LOG_KEY = "main"
    _LOOP_DELAY_MS = 1000
    
    # State Machine Constants
    _STATE_INIT = 0
    _STATE_IDLE = 1
    _STATE_STARTING_COMMAND = 2
    _STATE_RUNNING_COMMAND = 3
    _STATE_STOPPING_COMMAND = 4
    _STATE_PAUSE_BETWEEN_COMMANDS= 5
    _STATE_ERROR = 99
    
    # Private Class Members
    _run_main_loop = True
    _state = _STATE_INIT
    _command_queue = None
    _last_command_received = None
    _clear_queue = False
    _command_pause_timer = None
    
    '''Class Init - Initialize the Irrigation Controller with the logger and config manager'''
    def __init__(self, 
                 app_logger : logger.Logger, 
                 app_config : controller_config.ConfigManager):
        self.logger = app_logger
        self.config = app_config
        self._command_queue = command_queue.CommandQueue()
        
        # Create and start the MQTT Client
        self.mqtt_client = mqtt_client_pubsub.MqttClient(app_config, 
                                      app_logger, 
                                      self._new_message_callback, 
                                      self._publish_message_callback)
        self.mqtt_client.start()
        self.mqtt_client.subscribe(self.config.active_config['subscribe']['command_queue'])

    '''Blocking Run - Run the Irrigation Controller'''
    def run(self):
        zone_command = None

        while self._run_main_loop:
            
            # Check command flags
            if self._clear_queue:
                self._command_queue.empty_queue()
                self._clear_queue = False
                if zone_command is not None:
                    self._change_state(self._STATE_STOPPING_COMMAND)
                self._update_queue_status()
            
            # State Machine
            if self._state == self._STATE_INIT:
                self._command_queue.empty_queue()
                self._change_state(self._STATE_IDLE)
                zone_command = None
                self._command_pause_timer = None
                
            elif self._state == self._STATE_IDLE:
                '''Idle State - Waiting for a command to run / checking the command queue'''
                # Error Check - zone_command should be None 
                if not zone_command is None:
                    self.logger.write(self._LOG_KEY, "Zone Command is defined while machine is idle; resetting.", logger.MessageLevel.ERROR)
                    self._change_state(self._STATE_INIT)
                # Check if there are any commands in the queue
                if not self._command_queue.is_empty():
                    zone_command = self._command_queue.dequeue()
                    self._change_state(self._STATE_STARTING_COMMAND)
                    
            elif self._state == self._STATE_STARTING_COMMAND:
                ''' Start a command - set the zone state to active and start the timer'''
                command_success = self._set_zone_state(zone_command, True)
                if command_success:
                    self._change_state(self._STATE_RUNNING_COMMAND)
                else:
                    self._change_state(self._STATE_ERROR)
                
            elif self._state == self._STATE_RUNNING_COMMAND:
                self._update_queue_status(zone_command)
                # Check if the command is elapsed
                if zone_command.is_elapsed():
                    self._change_state(self._STATE_STOPPING_COMMAND)
                    

            elif self._state == self._STATE_STOPPING_COMMAND:
                ''' Stop a command - set the zone state to active and start the timer'''
                self.logger.write(self._LOG_KEY, f"Stopping valve {zone_command.zone.zone_name}...", logger.MessageLevel.INFO)
                command_success = self._set_zone_state(zone_command, False)
                self._command_pause_timer = elapsed_time.ElapsedTime(datetime.timedelta(seconds=self.config.active_config['delay_between_commands_secs']))
                if command_success:
                    self._change_state(self._STATE_PAUSE_BETWEEN_COMMANDS)
                    self.logger.write(self._LOG_KEY, f"{zone_command.zone.zone_name} stopped.", logger.MessageLevel.INFO)
                else:
                    self._change_state(self._STATE_ERROR)
                zone_command = None
            
            elif self._state == self._STATE_PAUSE_BETWEEN_COMMANDS:     
                self._update_queue_status()
                if self._command_pause_timer.is_elapsed():
                    self._change_state(self._STATE_IDLE)
                    
            elif self._state == self._STATE_ERROR:
                self.logger.write(self._LOG_KEY, "Error State - resetting to init.", logger.MessageLevel.ERROR)
            
            else:
                self.logger.write(self._LOG_KEY, "Unknown State - resetting to init.", logger.MessageLevel.ERROR)
            
            # Sleep for the loop delay
            time.sleep(self._LOOP_DELAY_MS / 1000)
            
    ''' -------------------- Private Class Members -------------------- '''
    def _change_state(self, new_state : int):
        '''Change the state of the Irrigation Controller'''
        self._state = new_state
        self.logger.write(self._LOG_KEY, f"Changing state to: {self._state_to_string()}", logger.MessageLevel.INFO)
        
        self._update_queue_status()
        
    def _update_queue_status(self, current_zone_command : zone.ZoneCommand = None):
        json_dict = defaultdict()
        json_dict['status_time'] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        json_dict['machine_state'] = self._state_to_string()
        json_dict['total_time_seconds'] = self._command_queue.total_command_time().total_seconds()
        # Current Zone Command
        if current_zone_command is not None:
            json_dict['running_zone'] = current_zone_command.zone.zone_name
            json_dict["remaining_time"] = current_zone_command.remaining_time().total_seconds()
        else:
            json_dict['running_zone'] = "None"
            json_dict["remaining_time"] = 0
        # List of remaining commands
        json_dict['commands'] = defaultdict()
        for command in self._command_queue.to_list():
            json_dict['commands'][command.zone.zone_name] = command
        # If Paused
        remaining_pause_seconds = 0
        if self._state == self._STATE_PAUSE_BETWEEN_COMMANDS:      
            if self._command_pause_timer is not None:
                remaining_pause_seconds = self._command_pause_timer.remaining_time().total_seconds()
        json_dict['remaining_pause_seconds'] = remaining_pause_seconds
        
        json_dict['last_command'] = self._last_command_received
        #json_str = json.dumps(json_dict)
        json_str = jsonpickle.encode(json_dict, unpicklable=False)
        self.mqtt_client.publish(self.config.active_config['publish']['queue_status'], json_str)
        
    def _state_to_string(self) -> str:
        '''Convert the state to a string'''
        if self._state == self._STATE_INIT:
            return "INIT"
        elif self._state == self._STATE_IDLE:
            return "IDLE"
        elif self._state == self._STATE_STARTING_COMMAND:
            return "STARTING_COMMAND"
        elif self._state == self._STATE_RUNNING_COMMAND:
            return "RUNNING_COMMAND"
        elif self._state == self._STATE_STOPPING_COMMAND:
            return "STOPPING_COMMAND"
        elif self._state == self._STATE_PAUSE_BETWEEN_COMMANDS:
            return "PAUSE_BETWEEN_COMMANDS"
        elif self._state == self._STATE_ERROR:
            return "ERROR"
        else:
            return "UNKNOWN"    
        
    def _new_message_callback(self, topic : str, message : str):
        '''Received a new message from the MQTT Broker'''
        self.logger.write(self._LOG_KEY, f"New message: {topic}->[{message}]", logger.MessageLevel.INFO)
        self._last_command_received = message.decode('utf-8')
        command_queue_topic = f"{self.config.active_config['base_topic']}/{self.config.active_config['subscribe']['command_queue']}"
        if topic == command_queue_topic:
            command_dict = json.loads(message.decode('utf-8'))
            if command_dict['Command'] == "Add":
                # Example: {"Command": "Add", "Zone_Index": 1, "Duration_Secs": 1200}
                zone_index = command_dict['Zone_Index']
                duration_seconds = command_dict['Duration_Secs']
                zone_record = self._get_zone_record_by_index(zone_index)
                if not zone_record is None:
                    zone_command = zone.ZoneCommand(zone_record, datetime.timedelta(seconds=duration_seconds))
                    self._command_queue.enqueue(zone_command)
                    self.logger.write(self._LOG_KEY, f"Added command for {zone_command.zone.zone_name}.", logger.MessageLevel.INFO)
                else:
                    self.logger.write(self._LOG_KEY, f"Failed to add command for {zone_command.zone_name}.", logger.MessageLevel.ERROR)
            elif command_dict['Command'] == "Clear":
                self._clear_queue = True
            else:
                self.logger.write(self._LOG_KEY, f"Unable to parse command: {message}", logger.MessageLevel.ERROR)
            
    def _get_zone_record_by_index(self, zone_index : int) -> zone.ZoneRecord:
        '''Get a zone record by the index'''
        for zone in self.config.active_config['zones'].values():
            if zone.zone_index == zone_index:
                return zone
        return None
    
    def _publish_message_callback(self, topic : str, message : str):
        self.logger.write(self._LOG_KEY, f"MQTT Msg Published: {topic}->{message}", logger.MessageLevel.INFO)
    
    def _set_zone_state(self, zone_command : zone.ZoneCommand, state : bool) -> bool:
        self.logger.write(self._LOG_KEY, f"Setting {zone_command.zone.zone_name} state to: [{state}]...", logger.MessageLevel.INFO)
        mqtt_topic = zone_command.zone.mqtt_command
        mqtt_command = '{"value": 1}' if state else '{"value": 0}'
        try:
            msg_info = self.mqtt_client.publish(mqtt_topic, mqtt_command, append_base=False)
            self.logger.write(self._LOG_KEY, f"{zone_command.zone.zone_name} state set to: [{state}].", logger.MessageLevel.INFO)
            zone_command.start()
            return True
        except Exception as e:
            self.logger.write(self._LOG_KEY, f"Failed to set {zone_command.zone.zone_name} state: {e}", logger.MessageLevel.ERROR)
            return False

if __name__ == "__main__":
    # Main variables
    log_key = "main"
    config_file = "default_irrigation_config.json"
    
    # Initialize Main object
    app_logger = logger.Logger()
    app_logger.write(log_key, "Initializing PumpBox Service...", logger.MessageLevel.INFO)
    
    # Load or create default config
    app_logger.write(log_key, "Loading config...", logger.MessageLevel.INFO)
    app_config = controller_config.ConfigManager(config_file, app_logger)
    
    # Create service object and run it
    app_logger.write(log_key, "Running Pump Box Service...", logger.MessageLevel.INFO)
    irrigation_controller = IrrigationController(app_logger, app_config)
    irrigation_controller.run()
    
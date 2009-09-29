"""
    OMERO.fs Monitor module for Window XP.


"""
import logging
import fsLogger
log = logging.getLogger("fsserver."+__name__)

import threading, Queue
import os, sys, traceback
import uuid
import time

# Third party path package. It provides much of the 
# functionality of os.path but without the complexity.
# Imported as pathModule to avoid clashes.
import path as pathModule

from omero.grid import monitors
from fsAbstractPlatformMonitor import AbstractPlatformMonitor

import win32file
import win32con

class PlatformMonitor(AbstractPlatformMonitor):
    """
        A Thread to monitor a path.
        
        :group Constructor: __init__
        :group Other methods: run, stop

    """
    def __init__(self, eventTypes, pathMode, pathString, whitelist, blacklist, ignoreSysFiles, ignoreDirEvents, proxy):
        """
            Set-up Monitor thread.
            
            After initialising the superclass and some instance variables
            try to create an FSEventStream. Throw an exeption if this fails.
            
            :Parameters:
                eventTypes : 
                    A list of the event types to be monitored.          
                    
                pathMode : 
                    The mode of directory monitoring: flat, recursive or following.

                pathString : string
                    A string representing a path to be monitored.
                  
                whitelist : list<string>
                    A list of files and extensions of interest.
                    
                blacklist : list<string>
                    A list of subdirectories to be excluded.

                ignoreSysFiles :
                    If true platform dependent sys files should be ignored.
                    
                monitorId :
                    Unique id for the monitor included in callbacks.
                    
                proxy :
                    A proxy to be informed of events         
        """
        AbstractPlatformMonitor.__init__(self, eventTypes, pathMode, pathString, whitelist, blacklist, ignoreSysFiles, ignoreDirEvents, proxy)

        self.actions = {
            1 : monitors.EventType.Create, # Created
            2 : monitors.EventType.Delete, # Deleted
            3 : monitors.EventType.Modify, # Updated
            4 : monitors.EventType.Modify, # Renamed to something
            5 : monitors.EventType.Modify  # Renamed from something
            }

        self.recurse = not (self.pathMode == "Flat")
        
        self.event = threading.Event()
        log.info('Monitor set-up on =' + str(self.pathsToMonitor))
        log.info('Monitoring %s events', str(self.eTypes))
                
    def run(self):
        """
            Start monitoring.
            
            :return: No explicit return value.
            
        """

        # Blocks
        self.watch() # for now
        
    def stop(self):        
        """
            Stop monitoring 
            
            :return: No explicit return value.
            
        """
        self.event.set()
        
    def watch(self):
        """
            Create a monitor on created files.
            
            Callback on file events.
            
        """

        FILE_LIST_DIRECTORY = 0x0001
        
        hDir = win32file.CreateFile (
            self.pathsToMonitor,
            FILE_LIST_DIRECTORY,
            win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE,
            None,
            win32con.OPEN_EXISTING,
            win32con.FILE_FLAG_BACKUP_SEMANTICS,
            None)

        while not self.event.isSet():
            results = win32file.ReadDirectoryChangesW (
                hDir,
                4096,
                self.recurse, # recurse
                win32con.FILE_NOTIFY_CHANGE_FILE_NAME |
                win32con.FILE_NOTIFY_CHANGE_DIR_NAME |
                win32con.FILE_NOTIFY_CHANGE_ATTRIBUTES |
                win32con.FILE_NOTIFY_CHANGE_SIZE |
                win32con.FILE_NOTIFY_CHANGE_LAST_WRITE |
                win32con.FILE_NOTIFY_CHANGE_SECURITY,
                None,
                None)

            eventList = []
            if results:
                for action, file in results:
                    filename = os.path.join(self.pathsToMonitor, file)
                    log.info("Event : %s %s", str(self.actions[action]), filename)    
                    if self.ignoreDirEvents and pathModule.path(filename).isdir():
                        log.info('Directory event, not propagated.')
                    else:
                        if action == 1:
                            if "Creation" in self.eTypes:
                                # Ignore default name for GUI created folders.
                                if self.ignoreSysFiles and filename.find('New Folder') >= 0:
                                    log.info('Created "New Folder" ignored.')
                                else:
                                    eventType = self.actions[action]
                                    # Should have richer filename matching here.
                                    if (len(self.whitelist) == 0) or (pathModule.path(filename).ext in self.whitelist):
                                        eventList.append((filename.replace('\\\\','\\').replace('\\','/'), eventType))
                            else:
                                log.info('Not propagated.')

                        elif action == 2:
                            if "Deletion" in self.eTypes:
                                # Ignore default name for GUI created folders.
                                if self.ignoreSysFiles and filename.find('New Folder') >= 0:
                                    log.info('Deleted "New Folder" ignored.')
                                else:
                                    eventType = self.actions[action]
                                    # Should have richer filename matching here.
                                    if (len(self.whitelist) == 0) or (pathModule.path(filename).ext in self.whitelist):
                                        eventList.append((filename.replace('\\\\','\\').replace('\\','/'), eventType))
                            else:
                                log.info('Not propagated.')

                        elif action in (3,4,5):
                            if "Modification" in self.eTypes:
                                # Ignore default name for GUI created folders.
                                if self.ignoreSysFiles and filename.find('New Folder') >= 0:
                                    log.info('Modified "New Folder" ignored.')
                                else:
                                    eventType = self.actions[action]
                                    # Should have richer filename matching here.
                                    if (len(self.whitelist) == 0) or (pathModule.path(filename).ext in self.whitelist):
                                        eventList.append((filename.replace('\\\\','\\').replace('\\','/'), eventType))
                            else:
                                log.info('Not propagated.')

                        else:
                            log.error('Unknown event type.')
                    
            if len(eventList) > 0:
                try:
                    log.info('Event notification => ' + str(eventList))
                    self.proxy.callback(eventList)
                except:
                    log.exception("Failed to make callback: ")

            
if __name__ == "__main__":
    class Proxy(object):
        def callback(self, eventList):
            for event in eventList:
                #pass
                log.info("EVENT_RECORD::%s::%s::%s" % (time.time(), event[1], event[0]))
    
    import logging
    from logging import handlers
    log = logging.getLogger("fstestserver")
    file_handler = logging.FileHandler("/TEST/logs/fstestserver.out")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(name)s - %(message)s"))
    log.addHandler(file_handler)
    log.setLevel(logging.INFO)
    log = logging.getLogger("fstestserver."+__name__)

    p = Proxy()
    m = PlatformMonitor([monitors.WatchEventType.Creation,monitors.WatchEventType.Modification], monitors.PathMode.Follow, "C:\OMERO\DropBox", [], [], True, True, p)
    try:
        m.start()
    except:
        m.stop()
    

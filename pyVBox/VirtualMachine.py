"""Wrapper around IMachine object"""

from Glue import IMediumToMedium
from Medium import Medium
from Progress import Progress
from Session import Session
from Snapshot import Snapshot
from StorageController import StorageController
from VirtualBox import VirtualBox
import VirtualBoxException
from VirtualBoxManager import Constants, VirtualBoxManager
from Wrapper import Wrapper

from contextlib import contextmanager
import os
import os.path

class VirtualMachine(Wrapper):
    # Properties directly inherited from IMachine
    _passthruProperties = [
        "accelerate2DVideoEnabled",
        "accelerate3DEnabled",
        "accessible",
        "CPUCount",
        "currentStateModified",
        "description",
        "guestPropertyNotificationPatterns",
        "HardwareVersion",
        "hardwareUUID",
        "id",
        "lastStateChange",
        "lockMachine",
        "logFolder",
        "memorySize",
        "monitorCount",
        "name",
        "OSTypeId",
        "sessionPid",
        "sessionState",
        "sessionType",
        "settingsFilePath",
        "settingsModified",
        "snapshotCount",
        "snapshotFolder",
        "state",
        "stateFilePath",
        "statisticsUpdateInterval",
        "teleporterAddress",
        "teleporterEnabled",
        "teleporterPassword",
        "teleporterPort",
        "unregister",
        "VRAMSize",
        ]

    _manager = VirtualBoxManager()
    _vbox = VirtualBox()

    def __init__(self, machine, session=None):
        """Return a VirtualMachine wrapper around given IMachine instance"""
        self._wrappedInstance = machine

    def __del__(self):
        pass

    def __str__(self):
        return self.name

    #
    # Top-level controls
    #
    def pause(self, wait=False):
        """Pause a running VM.

        If wait is True, then wait until machine is actually paused before returning."""
        with self.lock() as session:
            try:
                session.console.pause()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise
        # XXX Note sure if we need a lock for this or not
        if wait:
            self.waitUntilPaused()

    def resume(self):
        """Resume a paused VM."""
        with self.lock() as session:
            try:
                session.console.resume()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise

    def powerOff(self, wait=False):
        """Power off a running VM.

        If wait is True, then wait for power down and session closureto complete."""
        with self.lock() as session:
            try:
                session.console.powerDown()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise
        # XXX Not sure we need a lock for the following
        if wait:
            self.waitUntilDown()
            self.waitUntilUnlocked()

    def powerOn(self, type="gui", env=""):
        """Spawns a new process that executes a virtual machine.

        This is spawning a "remote session" in VirtualBox terms."""
        # TODO: Add a wait argument
        if not self.isRegistered():
            raise VirtualBoxException.VirtualBoxInvalidVMStateException(
                "VM is not registered")
        try:
            iMachine = self.getIMachine()
            session = Session.create()
            iprogress = iMachine.launchVMProcess(session.getISession(),
                                                 type, env)
            progress = Progress(iprogress)
            progress.waitForCompletion()
            session.unlockMachine()
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise

    def eject(self):
        """Do what ever it takes to unregister the VM"""
        if not self.isRegistered():
            # Nothing to do
            return
        if self.isRunning():
            self.powerOff(wait=True)
        self.unregister(cleanup_mode=Constants.CleanupMode_DetachAllReturnNone)

    def delete(self):
        """Do whatever it takes to delete the VM"""
        try:
            iMachine = self.getIMachine()
            iprogress = iMachine.delete(None)
            progress = Progress(iprogress)
            progress.waitForCompletion()
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        

    #
    # Creation methods
    #

    @classmethod
    def open(cls, path):
        """Opens a virtual machine from the existing settings file.

        Note that calling open() on a VM that is already registered will
        throw a VirtualBoxFileNotFoundException except.

        Throws VirtualBoxFileNotFoundException if file not found."""
        try:
            path = cls._canonicalizeVMPath(path)
            machine = cls._vbox.openMachine(path)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        return VirtualMachine(machine)

    @classmethod
    def find(cls, nameOrId):
        """Attempts to find a virtual machine given its name or UUID."""
        try:
            machine = cls._vbox.findMachine(nameOrId)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        return VirtualMachine(machine)

    @classmethod
    def get(cls, id):
        """Attempts to find a virtual machine given its UUID."""
        return cls.find(id)

    @classmethod
    def create(cls, name, osTypeId, baseFolder=None, id=None, register=True,
               forceOverwrite=False):
        """Create a new virtual machine with the given name and osType.
    
        If baseFolder is not None, it should be a path to use instead
        of the default machine settings folder for storing the VM.

        If id is not None, it will be used as the UUID of the
        machine. Otherwise one will be automatically generated.

        If register is True, register machine after creation."""
        try:
            machine = cls._vbox.createMachine(name,
                                              osTypeId,
                                              baseFolder,
                                              id,
                                              forceOverwrite)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        vm = VirtualMachine(machine)
        vm.saveSettings()
        if register:
            vm.register()
        return vm

    def clone(self, name, baseFolder=None, id=None, register=True,
              description=None):
        """Clone this virtual machine as new VM with given name.

        Clones basic properties of machine plus any storage
        controllers. Does not clone any attached storage.

        If baseFolder is not None, it should be a path to use instead
        of the default machine settings folder for storing the new VM.

        If id is not None, it will be used as the UUID of the
        new machine. Otherwise one will be automatically generated.

        If register is True, register new machine after creation.

        If description is None, copy description from source, otherwise use description."""
        vm = VirtualMachine.create(name,
                                   self.OSTypeId,
                                   baseFolder=baseFolder,
                                   id=id,
                                   # Once we register, we cannot make
                                   # changes without opening a
                                   # session, so defer any
                                   # registration.
                                   register=False)
        if description:
            vm.description = description
        else:
            vm.description = self.description
        vm.CPUCount = self.CPUCount
        vm.memorySize = self.memorySize
        vm.VRAMSize = self.VRAMSize
        vm.accelerate3DEnabled = self.accelerate3DEnabled
        vm.accelerate2DVideoEnabled = self.accelerate2DVideoEnabled
        vm.monitorCount = self.monitorCount
        controllers = self.getStorageControllers()
        for controller in controllers:
            vm.addStorageController(controller.bus,
                                    name = controller.name)
        vm.saveSettings()
        if register:
            vm.register()
        return vm

    @classmethod
    def getAll(cls):
        """Return an array of all known virtual machines"""
        return cls._vbox.machines
            
    #
    # Registration methods
    #

    def register(self):
        """Registers the machine within this VirtualBox installation."""
        try:
            self._vbox.registerMachine(self.getIMachine())
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise

    def unregister(self,
                   cleanup_mode=Constants.CleanupMode_DetachAllReturnNone):
        """Unregisters the machine previously registered using register()."""
        try:
            machine = self.getIMachine()
            machine.unregister(cleanup_mode)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise

    def isRegistered(self):
        """Is this virtual machine registered?"""
        from VirtualBoxException import VirtualBoxObjectNotFoundException
        try:
            VirtualMachine.get(self.id)
            registered = True
        except VirtualBoxObjectNotFoundException, e:
            registered = False
        except Exception, e:
            raise
        return registered

    #
    # Snapshot methods
    #
    def getCurrentSnapshot(self):
        """Returns current snapshot of this machine or None if machine currently has no snapshots"""
        imachine = self.getIMachine()
        if imachine.currentSnapshot is None:
            return None
        return Snapshot(imachine.currentSnapshot)

    def takeSnapshot(self, name, description=None, wait=True):
        """Saves the current execution state and all settings of the machine and creates differencing images for all normal (non-independent) media.

        Returns Progress instance. If wait is True, does not return until process completes."""
        assert(name is not None)
        with self.lock() as session:
            try:
                iprogress = session.console.takeSnapshot(name, description)
                progress = Progress(iprogress)
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise
        # XXX Not sure if we need a lock for this or not
        if wait:
            progress.waitForCompletion()
        return progress

    def deleteSnapshot(self, snapshot, wait=True):
        """Deletes the specified snapshot.

        Returns Progress instance. If wait is True, does not return until process completes."""
        assert(snapshot is not None)
        with self.lock() as session:
            try:
                iprogress = session.console.deleteSnapshot(snapshot.id)
                progress = Progress(iprogress)
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise
        # XXX Not sure if we need a lock for this or not
        if wait:
            progress.waitForCompletion()
        return progress

    #
    # Attribute getters
    #

    def getIMachine(self):
        """Return wrapped IMachine instance."""
        return self._wrappedInstance

    def getOSType(self):
        """Returns an object describing the specified guest OS type."""
        try:
            imachine = self.getIMachine()
            osType = self._vbox.getGuestOSType(imachine.OSTypeId)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        return osType

    #
    # Locking and unlocking
    #

    @contextmanager
    def lock(self, type=Constants.LockType_Shared):
        """Conextmaager yielding a session to a locked machine."""
        session = Session.create()
        try:
            self.getIMachine().lockMachine(session.getISession(), type)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        yield session
        session.unlockMachine(wait=True)

    def isLocked(self):
        """Does the machine have an open session?"""
        state = self.sessionState
        return ((state == Constants.SessionState_Locked) or
                (state == Constants.SessionState_Spawning) or
                (state == Constants.SessionState_Unlocking))

    def isUnlocked(self):
        """Does the VM not have an open session."""
        state = self.sessionState
        return ((state == Constants.SessionState_Null) or
                (state == Constants.SessionState_Unlocked))

    def waitUntilUnlocked(self):
        """Wait until VM is unlocked"""
        while not self.isUnlocked():
            self.waitForEvent()

    #
    # Attach methods
    #

    def attachDevice(self, medium):
        """Attachs a device. Requires an open session."""
        with self.lock() as session:
            try:
                # XXX following code needs to be smarter and find appropriate
                # attachment point
                storageControllers = self._getStorageControllers()
                storageController = storageControllers[0]
                controllerPort = 0
                device = 0
                deviceType = Constants.DeviceType_HardDisk
                session.getIMachine().attachDevice(storageController.name,
                                                   controllerPort,
                                                   device,
                                                   deviceType,
                                                   medium.getIMedium())
                session.saveSettings()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise

    def detachDevice(self, device):
        """Detach the device from the machine."""
        with self.lock() as session:
            try:
                attachment = self._findMediumAttachment(device)
                session.getIMachine().detachDevice(attachment.controller,
                                                   attachment.port,
                                                   attachment.device)
                session.saveSettings()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise

    def detachAllDevices(self):
        """Detach all devices from the machine."""
        with self.lock() as session:
            try:
                attachments = self._getMediumAttachments()
                for attachment in attachments:
                    session.getIMachine().detachDevice(attachment.controller,
                                                       attachment.port,
                                                       attachment.device)
                    session.saveSettings()
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise

    def getAttachedDevices(self):
        """Return array of attached Medium instances."""
        with self.lock() as session:
            mediums = []
            try:
                attachments = self._getMediumAttachments()
                attachments = filter(lambda a: a.medium is not None,
                                     attachments)
                mediums = [IMediumToMedium(a.medium) for a in attachments]
            except Exception, e:
                VirtualBoxException.handle_exception(e)
                raise
            return mediums

    def getHardDrives(self):
        """Return array of attached HardDrive instances."""
        return filter(lambda d: d.isHardDisk(), self.getAttachedDevices())

    #
    # StorageController methods
    #
    
    def getStorageControllers(self):
        """Return array of StorageControllers attached to this VM"""
        return [StorageController(c) for c in self._getStorageControllers()]

    def getStorageControllerByName(self, name):
        """Return the StorageController with the given name"""
        try:
            controller = self.getIMachine().getStorageControllerByName(name)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        return StorageController(controller)

    def getStorageControllerByInstance(self, instance):
        """Return the StorageController with the given instance number"""
        try:
            controller = self.getIMachine().getStorageControllerByInstance(instance)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        return StorageController(controller)

    def removeStorageController(self, name):
        """Removes a storage controller from the machine.

        Currently I'm getting a Operation aborted error invoking this method"""
        try:
            self.getIMachine().removeStorageController(name)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise

    def doesStorageControllerExist(self, name):
        """Return boolean indicating if StorageController with given name exists"""
        exists = False
        try:
            controller = self.getStorageControllerByName(name)
        except VirtualBoxException.VirtualBoxObjectNotFoundException, e:
            exists = False
        except:
            raise
        else:
            exists = True
        return exists

    def addStorageController(self, type, name=None):
        """Add a storage controller to the virtual machine

        type should be the bus type of the new controller. Must be one of Constants.StorageBus_IDE, Constants.StorageBus_SATA, Constants.StorageBus_SCSI, or Constants.StorageBus_Floppy

        name should be the name of the storage controller. If None, a name will be assigned.

        Returns StorageController instance for new controller.
        """
        if name is None:
            name = self._getNewStorageControllerName(type)
        try:
            controller = self.getIMachine().addStorageController(name, type)
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise
        session.saveSettings()
        return StorageController(controller)
        
    def _getNewStorageControllerName(self, type):
        """Choose a name for a new StorageController of the given type.

        Takes a string describing the controller type and adds an number to it to uniqify it if needed."""
        baseNames = {
            Constants.StorageBus_IDE    : "IDE Controller",
            Constants.StorageBus_SATA   : "SATA Controller",
            Constants.StorageBus_SCSI   : "SCSI Controller",
            Constants.StorageBus_Floppy : "Floppy Controller"
            }
        if not baseNames.has_key(type):
            # Todo: Use correct argument type here
            raise Exception("Invalid type '%d'" % type)
        count = 1
        name = baseNames[type]
        while self.doesStorageControllerExist(name):
            count += 1
            name = "%s %d" % (baseNames[type], count)
        return name

    #
    # Settings functions
    #

    def saveSettings(self):
        """Saves any changes to machine settings made since the session has been opened or a new machine has been created, or since the last call to saveSettings or discardSettings."""
        try:
            self.getIMachine().saveSettings()
        except Exception, e:
            VirtualBoxException.handle_exception(e)
            raise

    #
    # Monitoring methods
    #

    def waitForEvent(self):
        self._getManager().waitForEvents()

    def waitUntilRunning(self):
        """Wait until machine is running."""
        while not self.isRunning():
            self.waitForEvent()

    def waitUntilDown(self):
        """Wait until machine is down (cleanly or not)."""
        while not self.isDown():
            self.waitForEvent()

    def isDown(self):
        """Is machine down (PoweredOff, Aborted)?"""
        state = self.state
        if ((state == Constants.MachineState_Aborted) or
            (state == Constants.MachineState_PoweredOff)):
            return True
        return False

    def isRunning(self):
        """Is machine Running?"""
        state = self.state
        if (state == Constants.MachineState_Running):
            return True
        return False

    def isPaused(self):
        """Is machine Paused?"""
        state = self.state
        if (state == Constants.MachineState_Paused):
            return True
        return Fals

    def waitUntilPaused(self):
        """Wait until machine is paused."""
        while not self.isPaused():
            self.waitForEvent()

    #
    # Internal utility functions
    #
     
    @classmethod
    def _canonicalizeVMPath(cls, path):
        """Given a path to a VM do any needed clean up."""
        # path must be absolute path
        return os.path.abspath(path)

    def _findMediumAttachment(self, device):
        """Given a device, find the IMediumAttachment object associated with its attachment on this machine."""
        assert(device is not None)
        mediumAttachments = self._getMediumAttachments()
        for attachment in mediumAttachments:
            # medium can be Null for removable devices
            if attachment.medium is not None:
                if attachment.medium.id == device.id:
                    return attachment
        raise VirtualBoxException.VirtualBoxPluggableDeviceManagerError(
            "No attachment for device \"%s\" on VM \"%s\" found" % (device,
                                                                    self))


    #
    # Internal attribute getters
    #

    def _getArray(self, arrayName):
        """Return the array identified by the given name on this virtual machine."""
        return self._getManager().getArray(self.getIMachine(), arrayName)

    def _getManager(self):
        """Return the IVirtualBoxManager object associated with this VirtualMachine."""
        return self._manager

    def _getMediumAttachments(self):
        """Return the array of medium attachements on this virtual machine."""
        return self._getArray('mediumAttachments')

    def _getStorageControllers(self):
        """Return the array of storage controllers associated with this virtual machine."""
        return self._getArray('storageControllers')

# Simple implementation of IConsoleCallback
class VirtualMachineMonitor:
    def __init__(self, vm):
        self.vm = vm

    def onMousePointerShapeChange(self, visible, alpha, xHot, yHot,
                                  width, height, shape):
        pass

    def onMouseCapabilityChange(self, supportsAbsolute, needsHostCursor):
        pass

    def onKeyboardLedsChange(self, numLock, capsLock, scrollLock):
        pass

    def onStateChange(self, state):
        pass

    def onAdditionsStateChange(self):
        pass

    def onNetworkAdapterChange(self, adapter):
        pass

    def onSerialPortChange(self, port):
        pass

    def onParallelPortChange(self, port):
        pass

    def onStorageControllerChange(self):
        pass

    def onMediumChange(self, attachment):
        pass

    def onVRDPServerChange(self):
        pass

    def onRemoteDisplayInfoChange(self):
        pass

    def onUSBControllerChange(self):
        pass

    def onUSBDeviceStateChange(self, device, attached, error):
        pass

    def onSharedFolderChange(self, scope):
        pass

    def onRuntimeError(self, fatal, id, message):
        pass

    def onCanShowWindow(self):
        return True

    def onShowWindow(self, winId):
        pass

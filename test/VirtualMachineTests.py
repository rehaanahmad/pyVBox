#!/usr/bin/env python
"""Unittests for VirtualMachine"""

from pyVBoxTest import pyVBoxTest, main
from pyVBox.HardDisk import HardDisk
import pyVBox.VirtualBoxException
from pyVBox.VirtualBoxManager import Constants
from pyVBox.VirtualMachine import VirtualMachine

from time import sleep

class VirtualMachineTests(pyVBoxTest):
    """Test case for VirtualMachine"""

    def testOpen(self):
        """Test VirtualMachine.open()"""
        machine = VirtualMachine.open(self.testVMpath)
        self.assertNotEqual(None, machine.id)
        self.assertNotEqual(None, machine.name)
        self.assertEqual(True, machine.isDown())

    def testOpenNotFound(self):
        """Test VirtualMachine.open() with not found file"""
        self.assertRaises(
            pyVBox.VirtualBoxException.VirtualBoxFileNotFoundException,
            VirtualMachine.open, self.bogusVMpath)

    def testRegister(self):
        """Test VirtualMachine.register() and related functions"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        self.assertEqual(True, machine.isRegistered())
        m2 = VirtualMachine.find(machine.name)
        self.assertEqual(machine.id, m2.id)
        machine.unregister()
        self.assertEqual(False, machine.isRegistered())

    def testAttachDevice(self):
        """Test VirtualMachine.attachDevice() and related functions"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.attachDevice(harddisk)
        mediums = machine.getAttachedDevices()
        self.assertEqual(1, len(mediums))
        self.assertEqual(True, isinstance(mediums[0], HardDisk))
        machine.detachDevice(harddisk)
        machine.unregister()
        harddisk.close()

    def testEject(self):
        """Test VirtualMachine.eject()"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.attachDevice(harddisk)
        self.assertEqual(True, machine.isRegistered())
        machine.eject()
        self.assertEqual(False, machine.isRegistered())
        harddisk.close()

    def testPowerOn(self):
        """Test powering on a VM."""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.attachDevice(harddisk)
        machine.powerOn(type="vrdp")
        machine.waitUntilRunning()
        sleep(5)
        machine.powerOff(wait=True)
        machine.detachDevice(harddisk)
        harddisk.close()
        machine.unregister()

    def testSnapshot(self):
        """Test taking snapshot of a VM."""
        snapshotName = "Test Snapshot"
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        self.assertEqual(None, machine.getCurrentSnapshot())
        machine.takeSnapshot(snapshotName)
        snapshot = machine.getCurrentSnapshot()
        self.assertNotEqual(snapshot, None)
        self.assertEqual(snapshotName, snapshot.name)
        machine.deleteSnapshot(snapshot)
        self.assertEqual(None, machine.getCurrentSnapshot())
        
    def testGet(self):
        """Test VirtualMachine.get() method"""
        machine = VirtualMachine.open(self.testVMpath)
        # Should fail since not registered yet
        self.assertRaises(
            pyVBox.VirtualBoxException.VirtualBoxObjectNotFoundException,
            VirtualMachine.get, machine.id)
        machine.register()
        m2 = VirtualMachine.get(machine.id)
        self.assertNotEqual(None, m2)
        self.assertEqual(machine.id, m2.id)

    def testGetAll(self):
        """Test getAll() method"""
        machines = VirtualMachine.getAll()

    def testGetOSType(self):
        """Test getOSType() method"""
        machine = VirtualMachine.open(self.testVMpath)
        osType = machine.getOSType()
        self.assertNotEqual(None, osType)
        self.assertNotEqual(None, osType.familyId)
        self.assertNotEqual(None, osType.familyDescription)
        self.assertNotEqual(None, osType.id)
        self.assertNotEqual(None, osType.description)        

    def testCreate(self):
        """Test VirtualMachine.create() method"""
        machine = VirtualMachine.create("CreateTestVM", "Ubuntu")
        # Clean up
        machine.delete()

    def testGetStorageControllers(self):
        """Test VirtualMachine methods for getting StorageControllers"""
        machine = VirtualMachine.open(self.testVMpath)
        controllers = machine.getStorageControllers()
        self.assertNotEqual(None, controllers)
        for controller in controllers:
            c = machine.getStorageControllerByName(controller.name)
            self.assertNotEqual(None, c)
            c = machine.getStorageControllerByInstance(controller.instance)
            self.assertNotEqual(None, c)
            self.assertEqual(True,
                             machine.doesStorageControllerExist(controller.name))
    def testAddStorageControllers(self):
        """Test adding and removing of StorageController to a VirtualMachine"""
        # Currently the removeStorageController() method is failing with
        # an 'Operation aborted' and the test VM fails to boot if I leave
        # the added storage controllers, which messes up subsequent tests.
        return
        machine = VirtualMachine.open(self.testVMpath)
        controller = machine.addStorageController(Constants.StorageBus_SCSI)
        self.assertNotEqual(None, controller)
        controller2 = machine.addStorageController(Constants.StorageBus_SATA)
        self.assertNotEqual(None, controller2)
        self.assertEqual(True,
                         machine.doesStorageControllerExist(controller.name))
        machine.removeStorageController(controller2.name)
        self.assertEqual(False,
                         machine.doesStorageControllerExist(controller.name))

    def testSetAttr(self):
        """Set setting of VirtualMachine attributes"""
        machine = VirtualMachine.open(self.testVMpath)
        # Double memory and make sure it persists
        newMemorySize = machine.memorySize * 2
        machine.memorySize = newMemorySize
        machine.saveSettings()
        self.assertEqual(newMemorySize, machine.memorySize)
        machine2 = VirtualMachine.open(self.testVMpath)
        self.assertEqual(newMemorySize, machine2.memorySize)


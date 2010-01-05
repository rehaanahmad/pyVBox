#!/usr/bin/env python
"""Unittests for VirtualMachine"""

from pyVBoxTest import pyVBoxTest, main
from pyVBox.HardDisk import HardDisk
import pyVBox.VirtualBoxException
from pyVBox.VirtualMachine import VirtualMachine

from time import sleep

class VirtualMachineTests(pyVBoxTest):
    """Test case for VirtualMachine"""

    def testOpen(self):
        """Test VirtualMachine.open()"""
        machine = VirtualMachine.open(self.testVMpath)
        id = machine.getId()
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
        self.assertEqual(True, machine.registered())
        m2 = VirtualMachine.find(machine.getName())
        self.assertEqual(machine.getId(), m2.getId())
        machine.unregister()
        self.assertEqual(False, machine.registered())

    def testSession(self):
        """Test VirtualMachine.openSession() and related functions"""
        machine = VirtualMachine.open(self.testVMpath)
        self.assertEqual(False, machine.hasDirectSession())
        self.assertRaises(
            pyVBox.VirtualBoxException.VirtualBoxInvalidVMStateException,
            machine.openSession)
        machine.register()
        machine.openSession()
        self.assertEqual(True, machine.hasDirectSession())
        machine.closeSession()
        self.assertEqual(False, machine.hasDirectSession())
        machine.unregister()

    def testSessionDoubleOpen(self):
        """Testing for error on multiple calls to VirtualMachine.openSession()"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        machine.openSession()
        self.assertRaises(
            pyVBox.VirtualBoxException.VirtualBoxInvalidSessionStateException,
            machine.openSession)
        machine.closeSession()
        machine.unregister()

    def testAttachDevice(self):
        """Test VirtualMachine.attachDevice() and related functions"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.openSession()
        machine.attachDevice(harddisk)
        machine.detachDevice(harddisk)
        machine.closeSession()
        machine.unregister()
        harddisk.close()

    def testEject(self):
        """Test VirtualMachine.eject()"""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.openSession()
        machine.attachDevice(harddisk)
        self.assertEqual(True, machine.registered())
        machine.eject()
        self.assertEqual(False, machine.registered())
        harddisk.close()

    def testRemoteSession(self):
        """Test opening a remote session."""
        machine = VirtualMachine.open(self.testVMpath)
        machine.register()
        harddisk = HardDisk.open(self.testHDpath)
        machine.openSession()
        machine.attachDevice(harddisk)
        machine.closeSession()
        machine.openRemoteSession(type="vrdp")
        machine.waitUntilRunning()
        sleep(5)
        machine.powerOff()
        machine.waitUntilDown()
        machine.closeSession()
        machine.openSession()
        machine.detachDevice(harddisk)
        machine.closeSession()       
        harddisk.close()
        machine.unregister()

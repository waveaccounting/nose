"""
Result Proxy
------------

The result proxy wraps the result instance given to each test. It
performs two functions: enabling extended error/failure reporting,
including output capture, assert introspection, and varied error classes,
and calling plugins.

As each result event is fired, plugins are called with the same event;
however, plugins are called with the nose.case.Test instance that
wraps the actual test. So when a test fails and calls
result.addFailure(self, err), the result proxy calls
addFailure(self.test, err) for each plugin. This allows plugins to
have a single stable interface for all test types, and also to
manipulate the test object itself by setting the `test` attribute of
the nose.case.Test that they receive.
"""
import logging
import sys
import unittest
from nose.exc import SkipTest, DeprecatedTest
from nose.config import Config
from nose.inspector import inspect_traceback
from nose.util import ln, start_capture, end_capture

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO


log = logging.getLogger(__name__)

class ResultProxyFactory(object):
    """Factory for result proxies. Generates a ResultProxy bound to each test
    and the result passed to the test.
    """
    def __init__(self, config=None):
        if config is None:
            config = Config()
        self.config = config
        self.__prepared = False
        self.__result = None

    def __call__(self, result, test):
        """Return a ResultProxy for the current test.

        On first call, plugins are given a chance to replace the
        result used for the remaining tests. If a plugin returns a
        value from prepareTestResult, that object will be used as the
        result for all tests.
        """
        if not self.__prepared:
            plug_result = self.config.plugins.prepareTestResult(result)
            if plug_result is not None:
                self.__result = result = plug_result
        if self.__result is not None:
            result = self.__result
        return ResultProxy(result, test, config=self.config)


class ResultProxy(object):
    """Proxy to TestResults (or other results handler).

    One ResultProxy is created for each nose.case.Test. The result proxy
    handles processing the output capture and assert introspection duties,
    as well as calling plugins with the nose.case.Test instance (instead of the
    wrapped test case) as each result call is made. Finally, the real result
    method is called with the wrapped test.
    """    
    def __init__(self, result, test, config=None):
        if config is None:
            config = Config()
        self.config = config
        self.plugins = config.plugins
        self.result = result
        self.test = test

    def __repr__(self):
        return repr(self.result)

    def assertMyTest(self, test):
        # The test I was called with must be my .test or my
        # .test's .test.
        assert test is getattr(self.test, 'test', self.test), \
               "ResultProxy for %r was called with test %r" \
               % (self.test, test)

    def afterTest(self, test):
        self.assertMyTest(test)
        self.plugins.afterTest(self.test)
        try:
            self.result.beforeTest(test)
        except AttributeError:
            pass

    def beforeTest(self, test):
        self.assertMyTest(test)
        self.plugins.beforeTest(self.test)
        try:
            self.result.afterTest(test)
        except AttributeError:
            pass
        
    def addError(self, test, err):
        self.assertMyTest(test)
        plugins = self.plugins
        plugin_handled = plugins.handleError(test, err)
        if plugin_handled:
            return
        formatted = plugins.formatError(self.test, err)
        if formatted is not None:
            err = formatted
        # FIXME plugins expect capt
        plugins.addError(self.test, err)
        self.result.addError(test, err)

    def addFailure(self, test, err):
        self.assertMyTest(test)
        plugins = self.plugins
        plugin_handled = plugins.handleFailure(test, err)
        if plugin_handled:
            return
        formatted = plugins.formatFailure(self.test, err)
        if formatted is not None:
            err = formatted
        # FIXME plugins expect capt, tb info
        plugins.addFailure(self.test, err)
        self.result.addFailure(test, err)
    
    def addSuccess(self, test):
        self.assertMyTest(test)
        # FIXME plugins expect capt
        self.plugins.addSuccess(self.test)
        self.result.addSuccess(test)


    def formatErr(self, err, inspect_tb=False):
        capt = self.config.capture
        if not capt and not inspect_tb:
            return err
        ec, ev, tb = err
        if capt:
            self.test.captured_output = output = self.endCapture()
            self.startCapture()
            if output:
                ev = '\n'.join([str(ev) , ln('>> begin captured stdout <<'),
                                output, ln('>> end captured stdout <<')])
        if inspect_tb:
            tbinfo = inspect_traceback(tb)
            ev = '\n'.join([str(ev), tbinfo])
        return (ec, ev, tb)

    def startTest(self, test):
        self.assertMyTest(test)
        self.plugins.startTest(self.test)
        self.result.startTest(test)
    
    def stop(self):
        self.result.stop()
    
    def stopTest(self, test):
        self.plugins.stopTest(self.test)
        self.result.stopTest(test)
    
    def get_shouldStop(self):
        return self.result.shouldStop

    def set_shouldStop(self, shouldStop):
        self.result.shouldStop = shouldStop

    shouldStop = property(get_shouldStop, set_shouldStop, None,
                          """Should the test run stop?""")
    
# old

# class ResultProxy(Result):
#     """Result proxy. Performs nose-specific result operations, such as
#     handling output capture, inspecting assertions and calling plugins,
#     then delegates to another result handler.
#     """
#     def __init__(self, result):
#         self.result = result
    
#     def addError(self, test, err):
#         log.debug('Proxy addError %s %s', test, err)
#         Result.addError(self, test, err)
        
#         # compose a new error object that includes captured output
#         if self.capt is not None and len(self.capt):
#             ec, ev, tb = err
#             ev = '\n'.join([str(ev) , ln('>> begin captured stdout <<'),
#                             self.capt, ln('>> end captured stdout <<')])
#             err = (ec, ev, tb)
#         self.result.addError(test, err)
        
#     def addFailure(self, test, err):
#         log.debug('Proxy addFailure %s %s', test, err)
#         Result.addFailure(self, test, err)
        
#         # compose a new error object that includes captured output
#         # and assert introspection data
#         ec, ev, tb = err
#         if self.tbinfo is not None and len(self.tbinfo):
#             ev = '\n'.join([str(ev), self.tbinfo])
#         if self.capt is not None and len(self.capt):
#             ev = '\n'.join([str(ev) , ln('>> begin captured stdout <<'),
#                             self.capt, ln('>> end captured stdout <<')])
#         err = (ec, ev, tb)        
#         self.result.addFailure(test, err)
        
#     def addSuccess(self, test):
#         Result.addSuccess(self, test)
#         self.result.addSuccess(test)
    
#     def startTest(self, test):
#         Result.startTest(self, test)
#         self.result.startTest(test)

#     def stopTest(self, test):
#         Result.stopTest(self, test)
#         self.result.stopTest(test)

#     def _get_shouldStop(self):
#         return self.result.shouldStop

#     def _set_shouldStop(self, val):
#         self.result.shouldStop = val
        
#     shouldStop = property(_get_shouldStop, _set_shouldStop)

        
# class TestProxy(unittest.TestCase):
#     """Test case that wraps the test result in a ResultProxy.
#     """
#     resultProxy = ResultProxy
    
#     def __init__(self, wrapped_test):
#         self.wrapped_test = wrapped_test
#         log.debug('%r.__init__', self)
        
#     def __call__(self, *arg, **kw):
#         log.debug('%r.__call__', self)
#         self.run(*arg, **kw)

#     def __repr__(self):
#         return "TestProxy for: %r" % self.wrapped_test
        
#     def __str__(self):
#         return str(self.wrapped_test)    

#     def id(self):
#         return self.wrapped_test.id()
        
#     def run(self, result):
#         log.debug('TestProxy run test %s in proxy %s for result %s',
#                   self, self.resultProxy, result)
#         self.wrapped_test(self.resultProxy(result))

#     def shortDescription(self):
#         return self.wrapped_test.shortDescription()

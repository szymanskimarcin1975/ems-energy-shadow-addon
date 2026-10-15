"""Offline identity-gated monitoring; no signals or automatic restarts on UNKNOWN.

/proc observations are OS evidence, not HA/device timestamps. A PID is pinned to
its start ticks on launch. Failure to establish identity suspends supervision.
"""
import os
from pathlib import Path
from current_status import resource_sample_consistent
from progress_guard import ProgressGuard


def read_stat(pid):
    return Path('/proc', str(pid), 'stat').read_text()


def parse_identity(text):
    try:
        pid = int(text.split(' ', 1)[0])
        fields = text.rsplit(')', 1)[1].split()
        start = int(fields[19])
        if pid <= 0 or start < 0:
            raise ValueError()
        return pid, start
    except (ValueError, IndexError, AttributeError, TypeError):
        return None


class IdentityMonitor:
    def __init__(self, reader=read_stat, clock_ticks=None, page_size=None):
        self.reader = reader
        self.clock_ticks = clock_ticks or os.sysconf('SC_CLK_TCK')
        self.page_size = page_size or os.sysconf('SC_PAGE_SIZE')
        self.identity = None
        self.previous = None

    def pin(self, pid):
        """Double-read launch identity; no fallback to another process/self."""
        self.identity = None
        self.previous = None
        try:
            first = parse_identity(self.reader(pid))
            second = parse_identity(self.reader(pid))
        except (OSError, ValueError, TypeError):
            return False
        if first is None or first != second or first[0] != pid:
            return False
        self.identity = first
        return True

    def sample(self, monotonic_time):
        if self.identity is None:
            return self._unknown('identity_not_pinned')
        pid, start = self.identity
        try:
            text = self.reader(pid)
            sample = resource_sample_consistent(pid, start, text,
                                                self.previous)
        except (OSError, ValueError, TypeError):
            sample = None
        if sample is None:
            return self._unknown('identity_unavailable_or_mismatched')
        cpu_percent = None
        if self.previous is not None:
            elapsed = monotonic_time - self.previous['monotonic_time']
            if elapsed <= 0:
                return self._unknown('invalid_monitor_clock')
            cpu_percent = 100 * (sample['cpu_ticks'] - self.previous['cpu_ticks']) / self.clock_ticks / elapsed
        sample['monotonic_time'] = monotonic_time
        self.previous = sample
        return dict(state='VERIFIED', pid=pid, start_ticks=start,
                    rss_bytes=sample['rss_pages'] * self.page_size,
                    cpu_percent_one_core=cpu_percent,
                    automatic_restart_permitted=False)

    @staticmethod
    def _unknown(reason):
        return dict(state='UNKNOWN', reason=reason, rss_bytes=None,
                    cpu_percent_one_core=None, automatic_restart_permitted=False)


class IdentityProgressGuard(ProgressGuard):
    """Identity gates progress watchdog before it may send any termination signal.

    UNKNOWN is sticky. Explicit reconciliation outside this guard is required;
    even stop() sends no signals while target identity is unconfirmed.
    """
    def __init__(self, *args, identity_reader=read_stat, **kwargs):
        super().__init__(*args, **kwargs)
        self.identity_monitor = IdentityMonitor(identity_reader)
        self.resource_status = {'state': 'UNKNOWN'}

    def _unknown_identity(self):
        self.state = 'UNKNOWN'
        self.events.append('identity_unconfirmed_no_restart')

    def tick(self):
        import time
        if self.state in ('UNKNOWN', 'DISABLED', 'STOPPED'):
            return
        if self.child is not None and self.child.poll() is None:
            self.resource_status = self.identity_monitor.sample(time.monotonic())
            if self.resource_status['state'] != 'VERIFIED':
                self._unknown_identity()
                return
        before = self.child
        super().tick()
        if self.child is not None and self.child is not before:
            if not self.identity_monitor.pin(self.child.pid):
                self._unknown_identity()

    def shutdown(self):
        import time
        if self.child is not None and self.child.poll() is None:
            self.resource_status = self.identity_monitor.sample(time.monotonic())
            if self.resource_status['state'] != 'VERIFIED':
                self._unknown_identity()
                return False
        if self.state == 'UNKNOWN':
            return False
        return super().shutdown()

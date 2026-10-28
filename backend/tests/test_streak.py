from datetime import date

from app.models import User
from app.streak import current_streak, touch_streak


def test_consecutive_days_grow_streak():
    u = User(id=5, streak=0, longest_streak=0, last_seen_day=None)
    touch_streak(u, date(2026, 3, 10))
    assert u.streak == 1
    touch_streak(u, date(2026, 3, 10))  # повторный визит в тот же день ничего не меняет
    assert u.streak == 1
    touch_streak(u, date(2026, 3, 11))
    assert u.streak == 2 and u.longest_streak == 2


def test_missed_day_resets_but_keeps_longest():
    u = User(id=5, streak=0, longest_streak=0, last_seen_day=None)
    for day in (10, 11):
        touch_streak(u, date(2026, 3, day))
    touch_streak(u, date(2026, 3, 14))  # пропустили 12 и 13
    assert u.streak == 1 and u.longest_streak == 2


def test_current_streak_expires_after_gap():
    u = User(id=5, streak=4, longest_streak=4, last_seen_day="2026-03-10")
    assert current_streak(u, date(2026, 3, 10)) == 4
    assert current_streak(u, date(2026, 3, 11)) == 4  # вчера ещё считается
    assert current_streak(u, date(2026, 3, 12)) == 0  # день пропущен

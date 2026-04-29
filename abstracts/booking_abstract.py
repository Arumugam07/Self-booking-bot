from typing import Any

ATTRIBUTE_TEMPLATES = [
    ["days_in_view",            list],
    ["web_elements_in_view",    dict],
    ["times_in_view",           list],
    ["available_sessions",      dict],
    ["reserved_sessions",       dict],
    ["booked_sessions",         dict],
    ["lesson_name",             str],
    ["earlier_sessions",        dict],
    ["cached_earlier_sessions", dict],
    ["can_book_next",           bool],
]


class Types:
    SIMULATOR = "simulator"
    PRACTICAL = "practical"
    BTT       = "btt"
    RTT       = "rtt"
    FTT       = "ftt"
    PT        = "pt"

    @classmethod
    def all(cls):
        return [cls.SIMULATOR, cls.PRACTICAL, cls.BTT, cls.RTT, cls.FTT, cls.PT]


class CDCAbstract:
    def __init__(self, username, password, headless=False):
        self.username = username
        self.password = password
        self.headless  = headless

        for ft in Types.all():
            for attr_name, attr_type in ATTRIBUTE_TEMPLATES:
                default = True if attr_type is bool else attr_type()
                setattr(self, f"{attr_name}_{ft}", default)

        self.has_auto_reserved_simulator = False
        self.has_auto_reserved_practical = False

    def __str__(self):
        lines = ["# " + "-" * 70, "CDC STATE", ""]
        for ft in Types.all():
            lines.append(f"# {ft.upper()}")
            for attr_name, _ in ATTRIBUTE_TEMPLATES:
                val = getattr(self, f"{attr_name}_{ft}", None)
                lines.append(f"#   {attr_name} = {val}")
            lines.append("")
        lines.append("# " + "-" * 70)
        return "\n".join(lines)

    def get_attribute_with_fieldtype(self, attribute, field_type):
        return getattr(self, f"{attribute}_{field_type}")

    def set_attribute_with_fieldtype(self, attribute, field_type, value):
        setattr(self, f"{attribute}_{field_type}", value)

    def get_attribute(self, attribute):
        return getattr(self, attribute)

    def set_attribute(self, attribute, value):
        setattr(self, attribute, value)

    _WHITELISTED_FROM_RESET = {"cached_earlier_sessions"}

    def reset_attributes_for_all_fieldtypes(self):
        for ft in Types.all():
            self.reset_attributes_with_fieldtype(ft)

    def reset_attributes_with_fieldtype(self, field_type):
        for attr_name, attr_type in ATTRIBUTE_TEMPLATES:
            if attr_name in self._WHITELISTED_FROM_RESET:
                continue
            default = True if attr_type is bool else attr_type()
            setattr(self, f"{attr_name}_{field_type}", default)

        if field_type == Types.SIMULATOR:
            self.has_auto_reserved_simulator = False
        if field_type == Types.PRACTICAL:
            self.has_auto_reserved_practical = False

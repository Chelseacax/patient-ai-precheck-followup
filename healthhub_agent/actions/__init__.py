from actions.navigation import Login, NavigateTo, GoBack
from actions.appointments import ViewAppointments, BookAppointment, CancelAppointment
from actions.medications import ViewMedications
from actions.health_records import ViewHealthRecords, ViewLabResults

REGISTRY = {
    "login":               Login,
    "navigate_to":         NavigateTo,
    "go_back":             GoBack,
    "view_appointments":   ViewAppointments,
    "book_appointment":    BookAppointment,
    "cancel_appointment":  CancelAppointment,
    "view_medications":    ViewMedications,
    "view_health_records": ViewHealthRecords,
    "view_lab_results":    ViewLabResults,
}

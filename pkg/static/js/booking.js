// Booking Request Date Calculations
document.addEventListener('DOMContentLoaded', () => {
  const checkInInput = document.getElementById('check_in');
  const checkOutInput = document.getElementById('check_out');

  if (checkInInput && checkOutInput) {
    const today = new Date().toISOString().split('T')[0];
    checkInInput.setAttribute('min', today);

    checkInInput.addEventListener('change', () => {
      if (checkInInput.value) {
        const checkInDate = new Date(checkInInput.value);
        checkInDate.setDate(checkInDate.getDate() + 1);
        const minCheckOut = checkInDate.toISOString().split('T')[0];
        checkOutInput.setAttribute('min', minCheckOut);

        if (checkOutInput.value && checkOutInput.value <= checkInInput.value) {
          checkOutInput.value = minCheckOut;
        }
      }
    });
  }
});

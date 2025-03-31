// Get the button:
let mybutton = document.getElementById("myBtn");

// When the user scrolls down 20px from the top of the document, show the button
window.onscroll = function() {scrollFunction()};

function scrollFunction() {
  if (document.body.scrollTop > 20 || document.documentElement.scrollTop > 20) {
    mybutton.style.display = "block";
  } else {
    mybutton.style.display = "none";
  }
}

// When the user clicks on the button, scroll to the top of the document
function topFunction() {
  document.body.scrollTop = 0; // For Safari
  document.documentElement.scrollTop = 0; // For Chrome, Firefox, IE and Opera
}

// Theme Toggler Logic
document.addEventListener('DOMContentLoaded', (event) => {
    const themeToggleBtn = document.getElementById('themeToggleBtn'); // Target the button
    // const themeIcon = document.getElementById('themeIcon'); // No longer using separate icon span
    const htmlElement = document.documentElement; // Target the <html> element

    // Function to update the icon (No longer needed as CSS handles the SVG state)
    // const updateIcon = (theme) => { ... };

    // Apply the saved theme on initial load
    let currentTheme = localStorage.getItem('theme') ? localStorage.getItem('theme') : 'light'; // Default to light
    htmlElement.setAttribute('data-bs-theme', currentTheme);
    // updateIcon(currentTheme); // No longer needed

    // Add event listener for the theme toggle button
    themeToggleBtn.addEventListener('click', function() { // Listen on the button
        // Get the current theme attribute
        let theme = htmlElement.getAttribute('data-bs-theme');

        // Toggle theme
        if (theme === 'dark') {
            htmlElement.setAttribute('data-bs-theme', 'light');
            localStorage.setItem('theme', 'light');
            // updateIcon('light'); // No longer needed
        } else {
            htmlElement.setAttribute('data-bs-theme', 'dark');
            localStorage.setItem('theme', 'dark');
            // updateIcon('dark'); // No longer needed
        }
    });
});

function changeColor(elem) {
  if (elem.value == 0) {
    elem.style.color = '';
  } else {
    elem.style.color = '#333';
  }
}

function changeColor_w(elem) {
  if (elem.value == 0) {
    elem.style.color = '';
  } else {
    elem.style.color = '#fff';
  }
}

jQuery(function ($) {
  $(function () {
    $('header').click(function () {
      $('body').toggleClass('open');
    });
    $('#s-toggle').click(function () {
      $('body').toggleClass('s-open');
    });
  });
});

// メニュー（サイドバー）のドロワー開閉
const buttons = document.querySelectorAll('.menu-toggle');
const toggle = () => {
  if (!buttons[0]) return;
  buttons.forEach((btn) => {
    btn.addEventListener('click', () => {
      btn.classList.toggle('open');
    });
  });
};
toggle();
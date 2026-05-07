  jQuery(function ($) {
    $(function () {
        history.pushState(null, null, null);
        $(window).on('popstate', function(){
          history.pushState(null, null, null);
        });
    });
  });
$(function () {
    $.datepicker.setDefaults($.datepicker.regional["ja"]);
    $("#datepicker").datepicker();

    $('#searchForm').find('select').change(function () {
        document.search_form.submit();
    });

    $('#per').change(function () {
        document.search_form.submit();
    });

});
$('#datepicker').change(function () {
    var date = $(this).val();
    document.search_form.submit();
});
$('#number').change(function () {
    document.search_form.submit();
});

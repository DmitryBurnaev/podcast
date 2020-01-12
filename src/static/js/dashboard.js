// /* globals Chart:false, feather:false */
//
(function () {
    'use strict';
    $(document).ready(function () {
        $('.system-toast').toast('show');
        $('.add-episode').click(function () {
            $('#createEpisodeForm').attr('action', $(this).data('formAction'));
        });
        $('#copyLinkBtn').click(function () {
            var rssLink = $(this).data('rssLink');
            var el = document.createElement('textarea')
            var copyToast = $('#copyToast');

            el.value = rssLink;
            document.body.appendChild(el);
            el.select();
            document.execCommand('copy');
            document.body.removeChild(el);
            copyToast.toast('show');
        });
        // var acceptLanguage = navigator.language || navigator.userLanguage;
        // acceptLanguage = acceptLanguage.slice(0, 2)
        // TODO: use standard language for user's OS
        var acceptLanguage = "en"
        $('#languageSelect').val($.cookie("locale") || acceptLanguage || "en");
        $('#languageSelect').change(function () {
            $.cookie("locale", $(this).val(), {"path": "/"});
            location.reload();
        })
    })

}());

// /* globals Chart:false, feather:false */
//
(function () {
    'use strict';

    function invalidResponse(responseDetails){
        if (typeof responseDetails == "object"){
            for (var field in responseDetails){
                var input = $("input[name=" + field +"]");
                    input.addClass("is-invalid");
                var errorInfo = document.createElement("p");
                    errorInfo.setAttribute("class", "invalid-feedback invalid-signup");
                    errorInfo.innerText = responseDetails[field];
                $(errorInfo).insertAfter(input);
            }
        }
        else{
            var errorInfo = document.createElement("div");
                errorInfo.setAttribute("class", "alert alert-danger");
                errorInfo.setAttribute("role", "alert");
                errorInfo.innerText = responseDetails;

            $(errorInfo).insertBefore($("form"));
        }
    }
    function clearAlerts(){
        $(".invalid-feedback").remove();
        $(".is-invalid").removeClass("is-invalid");
        $(".alert").remove();
    }

    $(document).ready(function () {
        $("#signupFormID, #changePasswordFormID").submit(function(e) {
            e.preventDefault(); // avoid to execute the actual submit of the form
            var form = $(this);
            var url = form.attr('action');
            clearAlerts();

            $.ajax({
                type: "POST",
                url: url,
                data: form.serialize(), // serializes the form's elements.
            })
            .done(
                function(response){
                    window.location.href = response.redirect_url;
                }
            )
            .fail(
                function(response){
                    console.info(response);
                    invalidResponse(response.responseJSON.details)
                }
            );
        });
    })

}());

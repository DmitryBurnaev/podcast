// /* globals Chart:false, feather:false */
//
(function () {
    'use strict';



    function createEpisode(podcastId, video) {
        console.log("Create episode: ID: " + video.id + " URL: " + video.url)
        $.ajax({
            url: '/podcasts/' + podcastId + '/episodes/',
            method: 'POST',
            data: {'youtube_link': video.url},
            async:false
        }).done(function () {
            console.log("Episode created for VideoID: " + video.id)
            $("#statusIconVideo_" + video.id).find("svg").removeAttr("hidden")
        }).fail(function(response){console.info(response.responseJSON);});

    }

    function createEpisodes(podcastId){
        console.log("Create episodes", "podcast: ", podcastId);
        let inputs = $( "input:checked" );
        let videoItems = [];
        inputs.each(function(index, el){ videoItems.push({
            "id": $(el).data("videoId"),
            "url": $(el).data("videoUrl")
        }) })
        console.log(inputs);

        videoItems.forEach(function (video) {
            createEpisode(podcastId, video)
        })

    }

    function loadPlaylist(youtube_link){
        let dynamicPlaylistContent = $("#dynamicPlaylistContent");
        let loader = $("#loader")
        dynamicPlaylistContent.empty();
        loader.removeAttr("hidden");
        let playlist = {};
        $.ajax({
            url: '/api/playlist/',
            method: 'POST',
            data: {'playlist_url': youtube_link}
        }).done(function (response) {
            loader.attr("hidden", true)
            playlist = response;
            if (playlist.entries.length > 0){
                dynamicPlaylistContent.parent().removeClass("pb-3");
                $( "#playlistTemplate" ).tmpl( playlist.entries ).appendTo( "#dynamicPlaylistContent" );
                $("#createPlaylistEpisodes").attr("disabled", false)
            }else{
                dynamicPlaylistContent.parent().addClass("pb-3");
                dynamicPlaylistContent.html("No one videos found.")
            }
        }).fail(
            function(response){
                console.info(response.responseJSON);
            }
        );
    }


    $(document).ready(function () {

        $("#playlistURLFormID").submit(function(e) {
            e.preventDefault(); // avoid to execute the actual submit of the form
            let form = $(this);
            let youtube_link = form.find('input[name="youtube_link"]').val();
            loadPlaylist(youtube_link);
        });
        $("#createPlaylistEpisodes").click(function(button){
            let podcastId = $(this).data("podcastId")
            createEpisodes(podcastId)
        })
    })

}());

function alertbox(alrt,msg){
  return '<div class="alert alert-dismissible alert-'+alrt+'">\
    <button class="close" data-dismiss="alert" aria-label="close">&times;</button>\
    '+msg+'</div>'
}


$(function(){
  $('button[name=upvote]').click(function() {
    d = {'id': $(this).attr('id')};
    $.ajax({
      type: 'POST',
      url:'/_upvote',
      data: JSON.stringify(d),
      contentType: 'application/json;charset=UTF-8',
      success: function(response){
        if (response.result=='Success') {
          $("#alerts").append(alertbox('success','Thanks for your vote!'))
        } else {
          $("#alerts").append(alertbox('warning','You can only vote for this article once.'))
        }
      }
    })
    return false;
  });
})

$(function(){
  $('button[name=downvote]').click(function() {
    d = {'id': $(this).attr('id')};
    $.ajax({
      type: 'POST',
      url:'/_downvote',
      data: JSON.stringify(d),
      contentType: 'application/json;charset=UTF-8',
      success: function(response){
        if (response.result=='Success') {
          $("#alerts").append(alertbox('success','Thanks for your vote!'))
        } else {
          $("#alerts").append(alertbox('warning','You can only vote for this article once.'))
        }
      }
    })
    return false; // prevent default
  });
})

$(function(){
  $('button[name=notlogged]').click(function() {
    $("#alerts").append(
      alertbox('warning','You must be <strong><a href="login" class="alert-link">logged in</a></strong> to vote for articles.')
    );
  });
})

r = []; // current queue of articles

$(function(){
  $("button#query").click(function(){
    var dat = {}
    dat['s'] = $('input[name=searchstring]').val();
    $.ajax({
      type: 'POST',
      url:'/_query',
      data: JSON.stringify(dat),
      contentType: 'application/json;charset=UTF-8',
      success: function(response){
        //console.log(response.result);
        r = response.result;
        $('#select').show();
        $('#add').hide();
        $('.articlestats').empty();
        $('#acontain').empty();
        for (i = 0; i < r.length; i++) {
          rr = r[i]
          // pre = "<h4 class='list-group-item-heading'>"+rr.title+"</h4>"
          // post = "<p class='list-group-item-text'>"+rr.authors+" ("+rr.year+") <i>"+rr.source+"</i>, doi:"+rr.doi+"</p>"
          // content = pre + post
          // $("#acontain").append('<a href="#" id="'+i.toString()+'" class="list-group-item">'+content+'</a>');
          pre = "<span class='art'><input type='radio' name='article' value='"+i.toString()+"'></span><span class='art'>"
          if(rr.link == ""){
            title = "<u>"+rr.title+"</u><br> "
          }else{
            title = "<a href='"+rr.link+"'>"+rr.title+"</a><br> "
          }
          post = rr.authors+" ("+rr.year+") <i>"+rr.source+"</i>, doi:"+rr.doi+"</span>"
          content = pre + title + post
          $("#acontain").append('<div class="article">'+content+'</div>');
        }
      },
      error: function(error){
        console.log(error);
      }
    });
  })
});

$(function(){
  $("button#selectarticle").click(function(){
    id = $('input[name=article]:checked').val();
    aa = r[id];
    $('#select').hide();
    $('#add').show();
    pre = "<span class='art'>"
    if(aa.link == ""){
      title = aa.title+"<br> "
    }else{
      title = "<a href='"+aa.link+"'>"+aa.title+"</a></b><br> "
    }
    post = aa.authors+" ("+aa.year+") <i>"+aa.source+"</i>, doi:"+aa.doi+"</span>"
    content = pre + title + post
    $(".articlestats").append('<div class="selectedarticle" id="'+id+'">'+content+'</div>');
  })
});

$(function(){
  $("button#addarticle").click(function(){
    addart = r[$('.selectedarticle').attr('id')];
    addart['category'] = $('#category').val();
    addart['subcategory'] = null;//$('#subcategory').val();
    addart['keywords'] = $('input[name=keywords]').val();
    $.ajax({
      type: 'POST',
      url:'/_confirm',
      data: JSON.stringify(addart), // send along the selected result
      contentType: 'application/json;charset=UTF-8',
      success: function(response){
        $('#add').hide();
        $('#acontain').empty();
        $("#alerts").append(alertbox(response.status,response.result));
      },
      error: function(error){
        console.log(error);
      }
    });

  })
});

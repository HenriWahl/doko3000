let myname = ''

$(document).ready(function () {
    const socket = io({path: '/doko3000'})

    let dragging = dragula([document.querySelector('#hand'), document.querySelector('#table')]);

    dragging.on('drop', function(el) {
        console.log(el.id)
        console.log(el.parentNode.id)
        socket.emit('played-card', {card: el.id, username: myname})
    })

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('whoami')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (myname == '') {
            myname = msg.username
            console.log(myname)
        }
    })

    socket.on('my response', function (msg) {
        console.log(msg.data)
    })

    socket.on('session_available', function (msg) {
        console.log('yo')
        console.log(msg.data)
    })

    socket.on('thread_test', function (msg) {
        console.log('yolo')
        console.log(msg.data)
        console.log(myname)
    })

    socket.on('button-pressed-by-user', function (msg) {
        console.log(msg)
        console.log('myname:', myname)
        console.log(myname, msg.username, myname != msg.username)
        if (myname != msg.username) {
            console.log(msg.username, 'testbutton')
        }
    })

        socket.on('played-card-by-user', function (msg) {
        console.log(msg)
        console.log('myname:', myname)
        console.log(myname, msg.username, myname != msg.username)
        if (myname != msg.username) {
            console.log(msg.username, msg.card)
            $('#table').append($('#' + msg.card))
        }
    })


    $(document).on('click', '#testbutton', function () {
        console.log('testbutton')
        socket.emit('button-pressed', {button: 'testbutton'})
    })


})
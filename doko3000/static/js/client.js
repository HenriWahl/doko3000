let username = ''

$(document).ready(function () {
    const socket = io({path: '/doko3000'})

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('whoami')
    })

    socket.on('you-are-what-you-is', function (msg) {
        console.log(msg.username)
        username = msg.username
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
        console.log(username)
    })

    socket.on('button-pressed-by-user', function (msg) {
        console.log(msg.username)
    })

    $(document).on('click', '#testbutton', function () {
        console.log('testbutton')
        socket.emit('button-pressed', {button: 'testbutton'})
    })



})
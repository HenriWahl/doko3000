const socket = io( {path: '/doko3000'})

socket.on('connect', function () {
    socket.emit('my event',
        {data: 'I\'m connected!'})
})

socket.on('my response', function(msg) {
    console.log(msg.data)
})
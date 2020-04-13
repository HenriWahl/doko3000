let username = ''

$(document).ready(function () {
    const socket = io()

    let dragging = dragula([document.querySelector('#hand'),
        document.querySelector('#table'), {
            revertOnSpill: true
        }
    ]);

    dragging.on('drop', function (card, target, source) {
        console.log(target.id)
        console.log(source.id)
        if (source.id == 'hand' && target.id == 'table') {
            console.log(card.id)
            console.log(card.parentNode.id)
            console.log($(card).data('name'))
            socket.emit('played-card', {
                username: username,
                card_id: $(card).data('id'),
                card_name: $(card).data('name'),
                table: $(card).data('table')
            })
        } else if (source.id == 'table') {
            dragging.cancel(true)
        }
    })

    socket.on('connect', function () {
        socket.emit('my event',
            {data: 'I\'m connected!'})

        socket.emit('whoami')
    })

    socket.on('you-are-what-you-is', function (msg) {
        if (username == '') {
            username = msg.username
            console.log(username)
        }
    })

    socket.on('new-table-available', function (msg) {
        console.log(msg)
        console.log('username:', username)
        console.log(username, msg.username, username != msg.username)
        if (username != msg.username) {
            console.log(msg.username, 'testbutton')
        }
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        console.log(msg)
        console.log('username:', username)
        console.log(username, msg.username, username != msg.username)
        if (username != msg.username) {
            console.log(msg.username, msg.html)
            $('#table').append(msg.html)
        }
    })

    socket.on('grab-your-cards', function (msg) {
        console.log('response to grab-your-cards')
        console.log(msg)
        socket.emit('my-cards-please', {
            username: username,
            table: msg.table
        })
    })

    socket.on('your-cards-please', function (msg) {
        console.log('response to your-cards-please')
        console.log(msg)
        $('#table').html('Tisch')
        $('#hand').html(msg.html)
        if (msg.username == msg.next_player) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }

    })

    $(document).on('click', '#new_table', function () {
        console.log('new table')
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        console.log(this)
        console.log($(this).data('table'))
        socket.emit('enter-table', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#deal_cards', function () {
        console.log('deal cards')
        socket.emit('deal-cards', {
            username: username,
            table: $(this).data('table')
        })
    })


})
// globally used username
let username = ''
// for staying in sync with the game this is global
let turn_count = 0
// keep an eye on next player to know if turns are allowed or not
let next_player = ''

$(document).ready(function () {
    const socket = io()

    let dragging = dragula([document.querySelector('#hand'),
        document.querySelector('#table'), {
            revertOnSpill: true
        }
    ]);

    dragging.on('drop', function (card, target, source) {
        if (source.id == 'hand' && target.id == 'table' && username == next_player) {
            socket.emit('played-card', {
                username: username,
                card_id: $(card).data('id'),
                card_name: $(card).data('name'),
                table: $(card).data('table')
            })
        } else if (source.id == 'table' || username != next_player) {
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
        }
    })

    socket.on('new-table-available', function (msg) {
        $('#list_tables').html(msg.html)
    })

    socket.on('played-card-by-user', function (msg) {
        next_player = msg.next_player
        if (username != msg.username) {
            $('#table').append(msg.html)
        }
        if (msg.is_last_turn) {
            $('#turn_indicator').addClass('d-none')
            $('#claim_cards').removeClass('d-none')
        } else {
            if (username == next_player) {
                $('#turn_indicator').removeClass('d-none')
            } else {
                $('#turn_indicator').addClass('d-none')
            }
        }
    })

    socket.on('grab-your-cards', function (msg) {
        socket.emit('my-cards-please', {
            username: username,
            table: msg.table
        })
    })

    socket.on('your-cards-please', function (msg) {
        next_player = msg.next_player
        $('#table').html('Tisch')
        $('#hand').html(msg.html)
        if (msg.username == next_player) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }

    })

    socket.on('next-trick', function (msg) {
        next_player = msg.next_player
        $('#table').html('Tisch')
        if (msg.username == next_player) {
            $('#turn_indicator').removeClass('d-none')
        } else {
            $('#turn_indicator').addClass('d-none')
        }

    })

    $(document).on('click', '#new_table', function () {
        socket.emit('new-table', {button: 'new_table'})
    })

    $(document).on('click', '.list-item-table', function () {
        socket.emit('enter-table', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#deal_cards', function () {
        socket.emit('deal-cards', {
            username: username,
            table: $(this).data('table')
        })
    })

    $(document).on('click', '#claim_cards', function () {
        console.log('claim trick')
        socket.emit('claim-trick', {
            username: username,
            table: $(this).data('table')
        })
    })


})